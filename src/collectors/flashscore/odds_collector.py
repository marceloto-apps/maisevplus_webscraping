import asyncio
from datetime import datetime, timezone
from typing import List, Dict

from camoufox.async_api import AsyncCamoufox

from src.collectors.base import BaseCollector, CollectResult, CollectStatus
from src.collectors.flashscore.config import FlashscoreConfig, FLASHSCORE_BOOKMAKER_MAP
from src.collectors.flashscore.parser import FlashscoreParser
from src.normalizer.dedup import insert_odds_if_new
from src.db.pool import get_pool
from src.db.logger import get_logger

logger = get_logger(__name__)

class FlashscoreOddsCollector(BaseCollector):
    def __init__(self, markets: List[str] = None):
        super().__init__("flashscore")
        self.config = FlashscoreConfig()
        
        # Filtra quais mercados vamos scrapar
        if markets:
            self.markets_to_scrape = {k: v for k, v in self.config.markets.items() if k in markets}
        else:
            self.markets_to_scrape = self.config.markets
            
        self.bm_ids = {}

    async def health_check(self) -> bool:
        """Sempre retornamos True para Flashscore porque não depende de quota de chaves de API restritas."""
        return True

    async def _init_bm_ids(self, conn):
        if not self.bm_ids:
            # Busca todas as casas no banco para mapear strings para ints
            rows = await conn.fetch("SELECT bookmaker_id, name FROM bookmakers")
            for row in rows:
                self.bm_ids[row['name']] = row['bookmaker_id']

    async def collect_match(self, browser, conn, match_id_uuid: str, flashscore_id: str, is_closing: bool, job_id: str) -> int:
        """
        Para uma única partida, usa navegação SPA (cliques) para acessar a aba de odds.
        Flashscore bloqueia renderização de odds em navegação direta (goto);
        precisa simular clique real na aba Odds.
        Retorna quantidade de novos registros inseridos.
        """
        total_inserted = 0
        now = datetime.now(timezone.utc)
        
        page = await browser.new_page()
        try:
            # 1. Navegar para a página-resumo da partida
            base_url = f"https://www.flashscore.com/match/{flashscore_id}/"
            logger.debug(f"[Flashscore] Navegando para {base_url}")
            
            try:
                await page.goto(base_url, wait_until="domcontentloaded", timeout=self.config.page_timeout_ms)
            except Exception as e:
                logger.warning(f"[Flashscore] Timeout na página base de {flashscore_id}: {e}")

            # 2. Esperar e CLICAR na aba "ODDS" (navegação SPA)
            odds_tab = None
            try:
                await page.wait_for_selector("a[href*='/odds/']", timeout=15000)
                odds_tab = await page.query_selector("a[href*='/odds/']")
            except Exception:
                logger.warning(f"[Flashscore] Aba Odds não encontrada para {flashscore_id}")
                return 0
            
            if not odds_tab:
                logger.warning(f"[Flashscore] Aba Odds não encontrada para {flashscore_id}")
                return 0
            
            await odds_tab.click()
            logger.debug(f"[Flashscore] Cliquei na aba Odds de {flashscore_id}")
            
            # 3. Esperar a tabela de odds do primeiro mercado (1x2 FT) renderizar
            try:
                await page.wait_for_selector("div.ui-table__row", timeout=15000)
            except Exception:
                # Tenta seletor alternativo
                try:
                    await page.wait_for_selector("a.oddsCell__odd", timeout=5000)
                except Exception:
                    logger.warning(f"[Flashscore] Tabela de odds não renderizou para {flashscore_id}")
                    return 0
            
            # 4. Iterar pelos mercados — o primeiro (1x2_ft) já está carregado após o clique
            is_first_market = True
            for m_key, m_config in self.markets_to_scrape.items():
                logger.debug(f"[Flashscore] Coletando {m_key} para {flashscore_id}")
                
                try:
                    if not is_first_market:
                        # Para mercados subsequentes, clicar na sub-aba correspondente
                        # Converte: #/odds-comparison/1x2-odds/full-time -> 1x2-odds, full-time
                        market_parts = m_config["hash"].replace("#/odds-comparison/", "").split("/")
                        market_type_slug = market_parts[0] if market_parts else ""  # ex: "over-under"
                        period_slug = market_parts[1] if len(market_parts) > 1 else ""  # ex: "full-time"
                        
                        # Clicar na aba do tipo de mercado (ex: Over/Under, Asian Handicap, etc.)
                        market_tab = await page.query_selector(f"a[href*='/{market_type_slug}/']")
                        if not market_tab:
                            # Tenta buscar pelo texto do link nas sub-abas
                            logger.debug(f"[Flashscore] Sub-aba '{market_type_slug}' não encontrada, pulando {m_key}")
                            continue
                        
                        await market_tab.click()
                        await page.wait_for_timeout(500)
                        
                        # Se tem sub-período (full-time vs 1st-half), clicar nele também
                        if period_slug and period_slug != "full-time":
                            period_tab = await page.query_selector(f"a[href*='/{period_slug}']")
                            if period_tab:
                                await period_tab.click()
                                await page.wait_for_timeout(500)
                        
                        # Esperar re-render da tabela
                        try:
                            await page.wait_for_selector("div.ui-table__row", timeout=8000)
                        except Exception:
                            await page.wait_for_timeout(2000)
                    
                    is_first_market = False
                    
                    # Capturar HTML e parsear
                    html = await page.content()
                    odds_entries = FlashscoreParser.parse_odds_table(html, m_config, FLASHSCORE_BOOKMAKER_MAP)
                    logger.debug(f"[Flashscore] {m_key}: parsou {len(odds_entries)} linhas de odds")
                    
                    for entry in odds_entries:
                        our_bm_key = entry["bookmaker"]
                        bm_db_id = self.bm_ids.get(our_bm_key)
                        
                        if not bm_db_id:
                            continue
                            
                        is_new = await insert_odds_if_new(
                            conn=conn,
                            match_id=match_id_uuid,
                            bookmaker_id=bm_db_id,
                            market_type=entry["market_type"],
                            line=entry["line"],
                            period=entry["period"],
                            odds_1=entry["odds_1"],
                            odds_x=entry["odds_x"],
                            odds_2=entry["odds_2"],
                            source=self.source_name,
                            collect_job_id=job_id,
                            is_opening=False,
                            is_closing=is_closing,
                            time=now
                        )
                        if is_new:
                            total_inserted += 1
                            
                except Exception as e:
                    logger.warning(f"[Flashscore] Erro no mercado {m_key} para {flashscore_id}: {e}")
                    is_first_market = False  # Garante progressão mesmo com erro
                    
        finally:
            await page.close()
            
        return total_inserted

    async def collect(self, match_ids: List[dict] = None, is_closing: bool = False, **kwargs) -> CollectResult:
        """
        Ponto de entrada do BaseCollector.
        match_ids: lista de dicionários contendo {"match_id": UUID, "flashscore_id": str}
        is_closing: se True, marca as odds como is_closing = TRUE (útil para jogos pós match)
        """
        job_id = self.generate_job_id("flashscore_odds")
        started_at = datetime.now(timezone.utc)
        
        if not match_ids:
            return CollectResult(
                source=self.source_name, job_type="odds", job_id=job_id, status=CollectStatus.SUCCESS,
                started_at=started_at, finished_at=datetime.now(timezone.utc), records=[]
            )

        total_collected = 0
        total_new = 0
        total_skipped = 0
        errors = []

        pool = await get_pool()
        async with pool.acquire() as conn:
            await self._init_bm_ids(conn)
            
            # Aqui inicia o browser inteiro num contexto
            proxy = self.config.proxy
            if proxy:
                logger.info(f"[Flashscore] Usando proxy: {proxy['server']}")
            else:
                logger.warning("[Flashscore] Sem proxy configurado! Bookmakers podem ser regionais (não BR).")
            
            logger.info(f"[Flashscore] Iniciando browser (Headless={self.config.headless}) para {len(match_ids)} matches")
            
            try:
                # O wrapper AsyncCamoufox() precisa executar fetch internamente se não achar binário
                camoufox_kwargs = {"headless": self.config.headless, "os": "linux"}
                if proxy:
                    camoufox_kwargs["proxy"] = proxy
                    camoufox_kwargs["geoip"] = True
                async with AsyncCamoufox(**camoufox_kwargs) as browser:
                    for idx, m in enumerate(match_ids):
                        m_uuid = m["match_id"]
                        fs_id = m.get("flashscore_id")
                        
                        if not fs_id:
                            total_skipped += 1
                            continue
                            
                        logger.info(f"[Flashscore] Progresso: {idx+1}/{len(match_ids)} | Match: {fs_id}")
                        inserted = await self.collect_match(browser, conn, m_uuid, fs_id, is_closing, job_id)
                        
                        total_collected += 1  # Conta matches processados
                        total_new += inserted
                        
                        # Respeitar rate limits / evitar bans parecendo scripts
                        await asyncio.sleep(2)
                        
            except Exception as e:
                logger.error(f"[Flashscore] Erro crítico no Browser: {e}")
                errors.append(str(e))
                
        status = CollectStatus.FAILED if errors else CollectStatus.SUCCESS
        if errors and total_collected > 0:
            status = CollectStatus.PARTIAL
            
        return CollectResult(
            source=self.source_name,
            job_type="odds",
            job_id=job_id,
            status=status,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            records=[],
            records_collected=total_collected,
            records_new=total_new,
            records_skipped=total_skipped,
            errors=errors
        )
