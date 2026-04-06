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

    async def _resolve_odds_base_path(self, page, flashscore_id: str) -> str | None:
        """
        Navega até a página-resumo da partida e extrai o path base para a aba de odds.
        Retorna algo como '/match/football/gremio-xxx/remo-yyy/odds/' ou None.
        """
        base_url = f"https://www.flashscore.com/match/{flashscore_id}/"
        logger.debug(f"[Flashscore] Resolvendo slug em {base_url}")
        
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=self.config.page_timeout_ms)
        except Exception as e:
            logger.warning(f"[Flashscore] Timeout resolvendo base url para {flashscore_id}: {e}")

        # Espera as abas de navegação do match aparecerem (Summary, Odds, H2H, etc.)
        try:
            await page.wait_for_selector("a[href*='/odds/']", timeout=15000)
        except Exception:
            # Fallback: espera um tempo fixo generoso caso o seletor nunca apareça
            await page.wait_for_timeout(5000)
        
        # Tenta extrair da URL final (Flashscore pode redirecionar)
        final_url = page.url  # ex: https://www.flashscore.com/match/football/vitoria-xxx/sao-paulo-yyy/?mid=CxigkQ3L
        
        # Extrai o href via DOM
        odds_link = await page.query_selector(f"a[href*='/odds/'][href*='{flashscore_id}']")
        if odds_link:
            odds_href = await odds_link.get_attribute("href")
            if odds_href:
                base_path = odds_href.split("?")[0]
                if not base_path.endswith("/"):
                    base_path += "/"
                logger.debug(f"[Flashscore] Odds base path resolvido via DOM: {base_path}")
                return base_path
        
        # Fallback: tenta qualquer link com /odds/
        odds_link_any = await page.query_selector("a[href*='/odds/']")
        if odds_link_any:
            odds_href = await odds_link_any.get_attribute("href")
            if odds_href:
                base_path = odds_href.split("?")[0]
                if not base_path.endswith("/"):
                    base_path += "/"
                logger.debug(f"[Flashscore] Odds base path resolvido via fallback DOM: {base_path}")
                return base_path
        
        # Último fallback: construir a partir da URL final + /odds/
        import re
        match_path = re.search(r'(/match/football/[^?#]+)', final_url)
        if match_path:
            path = match_path.group(1).rstrip("/")
            constructed = f"{path}/odds/"
            logger.debug(f"[Flashscore] Odds base path construído da URL: {constructed}")
            return constructed
        
        return None

    async def collect_match(self, browser, conn, match_id_uuid: str, flashscore_id: str, is_closing: bool, job_id: str) -> int:
        """
        Para uma única partida, itera pelos mercados definidos e coleta as odds.
        Retorna quantidade de novos registros inseridos.
        """
        total_inserted = 0
        now = datetime.now(timezone.utc)
        
        page = await browser.new_page()
        try:
            # 1. Resolver o slug SEO-friendly
            base_odds_path = await self._resolve_odds_base_path(page, flashscore_id)
            
            if not base_odds_path:
                logger.warning(f"[Flashscore] Aba 'Odds' não encontrada para {flashscore_id}. Partida pode estar fechada sem odds ou muito no futuro.")
                return 0

            for m_key, m_config in self.markets_to_scrape.items():
                # Converte hash antigo para path novo
                # Hash: #/odds-comparison/1x2-odds/full-time  ->  Path: 1x2-odds/full-time
                market_path = m_config["hash"].replace("#/odds-comparison/", "")
                if market_path.startswith("/"):
                    market_path = market_path[1:]
                    
                target_url = f"https://www.flashscore.com{base_odds_path}{market_path}/?mid={flashscore_id}"
                logger.debug(f"[Flashscore] Coletando {m_key} em {target_url}")
                
                try:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=self.config.page_timeout_ms)
                    
                    # Espera a tabela de odds renderizar via JS
                    try:
                        await page.wait_for_selector("div.ui-table__row, a.oddsCell__odd", timeout=12000)
                    except Exception:
                        # Se timeout, tenta esperar mais um pouco - pode ser carregamento lento
                        await page.wait_for_timeout(3000)
                    
                    html = await page.content()
                    
                    # Parse HTML
                    odds_entries = FlashscoreParser.parse_odds_table(html, m_config, FLASHSCORE_BOOKMAKER_MAP)
                    logger.debug(f"[Flashscore] {m_key}: parsou {len(odds_entries)} linhas de odds")
                    
                    for entry in odds_entries:
                        our_bm_key = entry["bookmaker"]
                        bm_db_id = self.bm_ids.get(our_bm_key)
                        
                        if not bm_db_id:
                            continue
                            
                        # Insert deduplicado no DB
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
            logger.info(f"[Flashscore] Iniciando browser (Headless={self.config.headless}) para {len(match_ids)} matches")
            
            try:
                # O wrapper AsyncCamoufox() precisa executar fetch internamente se não achar binário
                async with AsyncCamoufox(headless=self.config.headless, os="linux") as browser:
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
