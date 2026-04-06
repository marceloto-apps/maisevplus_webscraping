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
        Para uma única partida, itera pelos mercados definidos e coleta as odds.
        Retorna quantidade de novos registros inseridos.
        """
        total_inserted = 0
        now = datetime.now(timezone.utc)
        
        page = await browser.new_page()
        try:
            # 1. Obter a URL base da partida para o JS resolver o slug real (SEO friendly)
            base_url = f"https://www.flashscore.com/match/{flashscore_id}/"
            logger.debug(f"[Flashscore] Resolvendo slug em {base_url}")
            
            try:
                await page.goto(base_url, wait_until="commit", timeout=self.config.page_timeout_ms)
            except Exception as e:
                logger.warning(f"[Flashscore] Timeout resolvendo base url para {flashscore_id}, tentando extrair: {e}")
                
            await page.wait_for_timeout(self.config.render_wait_ms)
            html_summary = await page.content()
            
            # Extrai o href aba odds
            from bs4 import BeautifulSoup
            soup_summary = BeautifulSoup(html_summary, "html.parser")
            odds_href = None
            for a in soup_summary.find_all("a"):
                href = str(a.get("href", ""))
                if "/odds/" in href and flashscore_id in href:
                    odds_href = href
                    break
                    
            if not odds_href:
                logger.warning(f"[Flashscore] Aba 'Odds' não encontrada para {flashscore_id}. Partida pode estar fechada sem odds ou muito no futuro.")
                return 0
                
            # Limpa o link para base. Ex: /match/football/gremio-X/remo-Y/odds/
            base_odds_path = odds_href.split("?")[0]
            if not base_odds_path.endswith("/"):
                base_odds_path += "/"

            for m_key, m_config in self.markets_to_scrape.items():
                # O hash velho era: #/odds-comparison/1x2-odds/full-time
                # Precisamos: /1x2-odds/full-time
                market_path = m_config["hash"].replace("#/odds-comparison/", "")
                if market_path.startswith("/"):
                    market_path = market_path[1:]
                    
                target_url = f"https://www.flashscore.com{base_odds_path}{market_path}/?mid={flashscore_id}"
                logger.debug(f"[Flashscore] Coletando {m_key} em {target_url}")
                
                try:
                    await page.goto(target_url, wait_until="commit", timeout=self.config.page_timeout_ms)
                    await page.wait_for_timeout(self.config.render_wait_ms)
                    
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
                            is_opening=False, # Flashscore displays pre-match current or closing if finished
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
