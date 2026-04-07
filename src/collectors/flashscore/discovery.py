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
        
        # Tenta fechar o banner de consentimento (se existir) porque ele tampa eventos de scroll/click
        try:
            cookie_btn = await page.query_selector('button#onetrust-accept-btn-handler')
            if cookie_btn and await cookie_btn.is_visible():
                await cookie_btn.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        max_attempts = 50
        for i in range(max_attempts):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)
            
            # Tenta pegar pela classe padrão
            more_btn = await page.query_selector('a.event__more')
            
            # Fallback 1: pegar pelo texto em Português
            if not more_btn:
                more_btn = await page.query_selector("text=Mostrar mais jogos")
                
            # Fallback 2: pegar pelo texto em Inglês
            if not more_btn:
                more_btn = await page.query_selector("text=Show more matches")
                
            if more_btn:
                try:
                    await more_btn.click(force=True)  # force=True ignora se tem outro elemento por cima
                    logger.debug(f"[FlashscoreDiscovery] Clicou em 'Mostrar mais jogos' (Tentativa {i+1})")
                    await page.wait_for_timeout(2500)  # Dá um tempo pro ajax trazer os elementos novos e injetar na DOM
                except Exception as e:
                    logger.debug(f"[FlashscoreDiscovery] Falha ao clicar no botão: {e}")
                    break
            else:
                logger.debug("[FlashscoreDiscovery] Fim do scroll: Botão não encontrado ou layout finalizado.")
                break

    async def _extract_matches_from_page(self, html: str, league_code: str, conn, url: str) -> int:
        soup = BeautifulSoup(html, "html.parser")
        updated_count = 0
        
        # Pega a season atual
        league_id = await conn.fetchval("SELECT league_id FROM leagues WHERE code = $1", league_code)
        if not league_id:
            return 0
        
        # Descobre o ano de início pela URL ou assume o ano atual
        recent_year = datetime.now().year
        match_years = re.search(r'-(\d{4})-(\d{4})/', url)
        if match_years:
            recent_year = int(match_years.group(2)) # Terminando ano da temporada europeia no topo (ex: maio de 2024)
        else:
            match_year = re.search(r'-(\d{4})/', url)
            if match_year:
                recent_year = int(match_year.group(1)) # Ano singular de estaduais / BR
                
        last_month = None

        for match_div in soup.find_all("div", id=re.compile(r"^g_1_")):
            try:
                # O ID vem no formato g_1_UUID (Flashscore)
                fs_id = match_div["id"].replace("g_1_", "")
                
                # Pega o texto principal pra extrair os times (eles tbm estão em classes separadas mas aqui é mais rapido)
                home_node = match_div.find("div", class_=re.compile("homeParticipant"))
                away_node = match_div.find("div", class_=re.compile("awayParticipant"))
                time_node = match_div.find("div", class_="event__time")
                
                if not home_node or away_node is None or not time_node:
                    continue
                    
                home_team = home_node.get_text(strip=True)
                away_team = away_node.get_text(strip=True)
                date_text = time_node.get_text(strip=True) # Ex: "22.03. 15:15" ou "16.12.2023 15:15"
                
                date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.\s*(\d{4})?', date_text)
                if date_match:
                    day = int(date_match.group(1))
                    month = int(date_match.group(2))
                    explicit_year_str = date_match.group(3)
                    
                    if explicit_year_str:
                        # O Flashscore imprimiu o ano explicitamente (comum para datas de ano(s) anterior(es))
                        recent_year = int(explicit_year_str)
                    else:
                        # O ano está oculto (ex: '22.03. 15:15'), usamos tracking progressivo
                        if last_month is not None:
                            if last_month <= 6 and month >= 8:
                                recent_year -= 1
                            elif last_month >= 8 and month <= 6:
                                recent_year += 1
                                
                    last_month = month
                    
                    match_date = datetime(recent_year, month, day).date()
                    
                    print(f"Tentando resolver: {home_team} vs {away_team} at {match_date}")
                    
                    # Resolve
                    match_uuid = await MatchResolver.resolve(league_id, home_team, away_team, match_date, "flashscore")
                    
                    if match_uuid:
                        # Verifica se já tem fs_id ou se já não está preenchido com esse
                        current_fs_id = await conn.fetchval("SELECT flashscore_id FROM matches WHERE match_id = $1", match_uuid)
                        if current_fs_id != fs_id:
                            await conn.execute("UPDATE matches SET flashscore_id = $1 WHERE match_id = $2", fs_id, match_uuid)
                            updated_count += 1
                            print(f"  --> SUCESSO: Associado e atualizado (fs_id={fs_id})")
                    else:
                        print(f"[FlashscoreDiscovery] Não resolvido no BD: {home_team} x {away_team} em {match_date} ({fs_id})")
                        
            except Exception as e:
                print(f"[FlashscoreDiscovery] Falha num HTML match node: {e}")
                
        return updated_count

    async def collect(self, mode: str = "fixtures", specific_leagues: List[str] = None, target_urls: Dict[str, List[str]] = None, **kwargs) -> CollectResult:
        """
        Ponto de entrada do BaseCollector.
        Mode: "fixtures" (jogos futuros) ou "results" (jogos terminados recentes)
        target_urls: { "ENG_PL": ["https://www.flashscore.com/..."] }
        """
        job_id = self.generate_job_id(f"flashscore_discovery_{mode}")
        started_at = datetime.now(timezone.utc)
        
        from src.normalizer.team_resolver import TeamResolver
        await TeamResolver.load_cache()
        
        leagues_to_run = specific_leagues or list(LEAGUE_FLASHSCORE_PATHS.keys())
        
        total_updated = 0
        errors = []
        
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with AsyncCamoufox(headless=self.config.headless, os="linux") as browser:
                page = await browser.new_page()
                
                for league_code in leagues_to_run:
                    urls = []
                    if target_urls and league_code in target_urls:
                        urls = target_urls[league_code]
                    else:
                        path = LEAGUE_FLASHSCORE_PATHS.get(league_code)
                        if not path:
                            continue
                        urls = [f"https://www.flashscore.com/{path}/{mode}/"]
                        
                    for url in urls:
                        print(f"\n[Flashscore] Discovery URL alvo: {url}")
                    
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=self.config.page_timeout_ms)
                        
                        # Espera explícita pelo primeiro jogo renderizar (sinal que o JS principal rodou)
                        try:
                            await page.wait_for_selector('div[id^="g_1_"]', timeout=15000)
                        except Exception:
                            logger.warning(f"[Flashscore] Timeout esperando os jogos carregarem em: {url}")
                            # Continua para tentar mesmo assim (pode não haver jogos listados)
                        
                        # Dá um tempo a mais pro layout estabilizar
                        await page.wait_for_timeout(self.config.render_wait_ms)
                        
                        await self._scroll_page(page)
                        
                        html = await page.content()
                        
                        # Process HTML e update BD
                        upd = await self._extract_matches_from_page(html, league_code, conn, url)
                        total_updated += upd
                        print(f"[Flashscore] {league_code}: {upd} novos flashscore_ids atualizados na base de dados.\n")
                        
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
