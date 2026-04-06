import asyncio
import re
from datetime import datetime, timezone
from typing import List, Dict

from camoufox.async_api import AsyncCamoufox
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector, CollectResult, CollectStatus
from src.collectors.flashscore.config import FlashscoreConfig, LEAGUE_FLASHSCORE_PATHS
from src.db.pool import get_pool
from src.db.logger import get_logger
from src.normalizer.match_resolver import MatchResolver

logger = get_logger(__name__)

class FlashscoreDiscovery(BaseCollector):
    """
    Coleta IDs de partidas do Flashscore (fixtures ou results) e mapeia
    para nossa tabela `matches`, gravando em `flashscore_id`.
    """
    def __init__(self):
        super().__init__("flashscore")
        self.config = FlashscoreConfig()

    async def health_check(self) -> bool:
        """Sempre retornamos True para Flashscore porque não depende de quota de chaves de API restritas."""
        return True

    async def _scroll_page(self, page):
        """Scrolla a página para tentar carregar mais jogos dinamicamente no Flashscore."""
        for _ in range(self.config.discovery_max_scrolls):
            # Click no botão "Show more matches" se existir
            more_btn = await page.query_selector('a.event__more')
            if more_btn:
                try:
                    await more_btn.click()
                    await page.wait_for_timeout(1000)
                except Exception:
                    pass
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

    async def _extract_matches_from_page(self, html: str, league_code: str, conn) -> int:
        """
        Extrai as informações de cada partida renderizada (casa, fora, data) e tenta
        gravar o flashscore_id no banco usando o MatchResolver.
        Retorna o número de matches atualizados.
        """
        soup = BeautifulSoup(html, "html.parser")
        match_divs = soup.find_all("div", id=re.compile(r"^g_1_"))
        
        if not match_divs:
            logger.warning(f"No match divs found in HTML for {league_code}. Check DOM selectors.")
            
        updated_count = 0
        
        # Pega a season atual
        league_id = await conn.fetchval("SELECT league_id FROM leagues WHERE code = $1", league_code)
        if not league_id:
            return 0

        for index, div in enumerate(match_divs):
            try:
                fs_id = div['id'].replace("g_1_", "")
                
                # Debug logging for the very first div
                if index == 0:
                    logger.debug(f"FIRST MATCH DIV FULL DOM:\n{div.prettify()}")
                
                home_elem = div.find("div", class_=lambda c: c and "participant--home" in c)
                away_elem = div.find("div", class_=lambda c: c and "participant--away" in c)
                time_elem = div.find("div", class_=lambda c: c and "event__time" in c)
                
                if not home_elem or not away_elem or not time_elem:
                    logger.debug(f"Missing elems: home={bool(home_elem)}, away={bool(away_elem)}, time={bool(time_elem)}")
                    continue
                    
                home_team = home_elem.get_text(strip=True)
                away_team = away_elem.get_text(strip=True)
                time_text = time_elem.get_text(strip=True)
                
                # Formato temporal flashscore: "14.05. 16:00" ou "24.08.2025 15:30" (menos comum)
                day_month = re.search(r"(\d{2})\.(\d{2})\.", time_text)
                if not day_month:
                    logger.debug(f"Regex failed for time format: {time_text}")
                    continue
                    
                day = int(day_month.group(1))
                month = int(day_month.group(2))
                
                # Lógica simplificada de Ano (M1) — pega do now ou now+1 se o mes atual for maior
                now = datetime.now()
                year = now.year
                if month > now.month + 6:
                    year -= 1 # provavelmente do início da season europeia do ano passado
                elif month < now.month - 6:
                    year += 1 # fim da season no ano que vem
                    
                match_date = datetime(year, month, day).date()
                
                logger.info(f"Trying to resolve: {home_team} vs {away_team} at {match_date}")
                
                # Resolve
                match_uuid = await MatchResolver.resolve(league_id, home_team, away_team, match_date, "flashscore")
                
                if match_uuid:
                    # Verifica se já tem fs_id ou se já não está preenchido com esse
                    current_fs_id = await conn.fetchval("SELECT flashscore_id FROM matches WHERE match_id = $1", match_uuid)
                    if current_fs_id != fs_id:
                        await conn.execute("UPDATE matches SET flashscore_id = $1 WHERE match_id = $2", fs_id, match_uuid)
                        updated_count += 1
                else:
                    logger.debug(f"[FlashscoreDiscovery] Não resolvido: {home_team} x {away_team} em {match_date} ({fs_id})")
                    
            except Exception as e:
                logger.warning(f"[FlashscoreDiscovery] Falha num HTML match node: {e}")
                
        return updated_count

    async def collect(self, mode: str = "fixtures", specific_leagues: List[str] = None, **kwargs) -> CollectResult:
        """
        Ponto de entrada do BaseCollector.
        Mode: "fixtures" (jogos futuros) ou "results" (jogos terminados recentes)
        """
        job_id = self.generate_job_id(f"flashscore_discovery_{mode}")
        started_at = datetime.now(timezone.utc)
        
        leagues_to_run = specific_leagues or list(LEAGUE_FLASHSCORE_PATHS.keys())
        
        total_updated = 0
        errors = []
        
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with AsyncCamoufox(headless=self.config.headless, os="linux") as browser:
                page = await browser.new_page()
                
                for league_code in leagues_to_run:
                    path = LEAGUE_FLASHSCORE_PATHS.get(league_code)
                    if not path:
                        continue
                        
                    # Base URL: https://www.flashscore.com/football/england/premier-league/
                    url = f"https://www.flashscore.com/{path}/{mode}/"
                    logger.info(f"[Flashscore] Discovery URL: {url}")
                    
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=self.config.page_timeout_ms)
                        # Dá um tempo pro JS renderizar
                        await page.wait_for_timeout(self.config.render_wait_ms)
                        
                        await self._scroll_page(page)
                        
                        html = await page.content()
                        
                        # Process HTML e update BD
                        upd = await self._extract_matches_from_page(html, league_code, conn)
                        total_updated += upd
                        logger.info(f"[Flashscore] {league_code}: {upd} flashscore_ids atualizados.")
                        
                        await asyncio.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"[Flashscore] Falha no discovery para {league_code}: {e}")
                        errors.append(str(e))
                        
                await page.close()
                

        return CollectResult(
            source=self.source_name,
            job_type=f"discovery_{mode}",
            job_id=job_id,
            status=CollectStatus.FAILED if len(errors) == len(leagues_to_run) else CollectStatus.SUCCESS,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            records=[],
            records_new=total_updated,
            errors=errors
        )
