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
from src.normalizer.team_resolver import TeamResolver

logger = get_logger(__name__)

# Padrões de sufixo que o Flashscore injeta como elementos filho dentro do nó do participante.
# Ex: "Beerschot VAAdvancing to next round: Beerschot VA" → "Beerschot VA"
#     "OldhamWinner" → "Oldham"
_TEAM_SUFFIX_RE = re.compile(
    r'(Advancing to next round.*|Winner.*|Eliminated.*|Qualified.*|Relegated.*|Promoted.*)$',
    re.IGNORECASE
)

def _extract_team_name(node) -> str:
    """
    Extrai o nome limpo do time de um nó BeautifulSoup do tipo homeParticipant/awayParticipant.

    O Flashscore injeta elementos filho com textos de status ("Winner", "Advancing to next round: X",
    etc.) dentro do mesmo nó pai. O get_text() ingênuo os concatena ao nome.

    Estratégia:
      1. Tenta encontrar o elemento específico do nome do time via classes 'name' ou atributo data-testid.
      2. Se não encontrar, tenta o primeiro NavigableString direto do nó.
      3. Como último recurso, clona o nó, remove tags de metadados indesejados (SVG, button) e extrai o texto.
    """
    # 1. Tentar encontrar o elemento específico do nome do time (span com classe contendo 'name')
    name_el = node.find(class_=re.compile(r'name|participantName', re.I))
    if not name_el:
        name_el = node.find(attrs={"data-testid": "wcl-scores-simple-text-01"})
    
    if name_el:
        raw = name_el.get_text(strip=True)
        return _TEAM_SUFFIX_RE.sub("", raw).strip()

    from bs4 import NavigableString
    # 2. Primeiro NavigableString direto — geralmente é o nome puro do time
    for child in node.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                return text

    # 3. Fallback: get_text() completo, mas antes clona e decompõe elementos indesejados (SVG com cartões vermelhos, etc.)
    import copy
    node_copy = copy.copy(node)
    for bad_tag in node_copy.find_all(['svg', 'button', 'script', 'style']):
        bad_tag.decompose()
        
    raw = node_copy.get_text(strip=True)
    return _TEAM_SUFFIX_RE.sub("", raw).strip()


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

    async def _extract_matches_from_page(self, html: str, league_code: str, conn, url: str, season_id: int, mode: str) -> int:
        soup = BeautifulSoup(html, "html.parser")
        updated_count = 0
        
        # Recupera informações da liga
        league_row = await conn.fetchrow(
            "SELECT league_id, country, primary_source FROM leagues WHERE code = $1", 
            league_code
        )
        if not league_row:
            return 0
        league_id = league_row["league_id"]
        league_country = league_row["country"]
        primary_source = league_row["primary_source"]
        
        # Descobre o ano de início pela URL ou assume o ano atual
        recent_year = datetime.now().year
        match_years = re.search(r'-(\d{4})-(\d{4})/', url)
        if match_years:
            recent_year = int(match_years.group(2)) # Terminando ano da temporada europeia no topo (ex: maio de 2024)
        else:
            match_year = re.search(r'-(\d{4})/', url)
            if match_year:
                recent_year = int(match_year.group(1)) # Ano singular de estaduais / BR
                
        # Helper interno para resolver ou auto-criar time se a fonte for flashscore
        async def get_or_create_team(name: str) -> int:
            tid = await TeamResolver.resolve("flashscore", name)
            if tid is not None:
                return tid
            
            if primary_source == 'flashscore':
                # Verifica se o time existe no banco (case-insensitive)
                db_tid = await conn.fetchval(
                    "SELECT team_id FROM teams WHERE LOWER(name_canonical) = LOWER($1) AND country = $2",
                    name, league_country
                )
                if db_tid:
                    tid = db_tid
                else:
                    tid = await conn.fetchval(
                        "INSERT INTO teams (name_canonical, country) VALUES ($1, $2) RETURNING team_id",
                        name, league_country
                    )
                # Insere o alias correspondente
                await conn.execute(
                    "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'flashscore', $2) ON CONFLICT DO NOTHING",
                    tid, name
                )
                # Adiciona ao cache do resolver
                TeamResolver.add_to_cache("flashscore", name, tid)
                return tid
            return None

        for match_div in soup.find_all("div", id=re.compile(r"^g_1_")):
            try:
                fs_id = match_div["id"].replace("g_1_", "")
                
                home_node = match_div.find("div", class_=re.compile("homeParticipant"))
                away_node = match_div.find("div", class_=re.compile("awayParticipant"))
                time_node = match_div.find("div", class_="event__time")
                
                if not home_node or away_node is None or not time_node:
                    continue
                    
                home_team = _extract_team_name(home_node)
                away_team = _extract_team_name(away_node)
                date_text = time_node.get_text(strip=True) # Ex: "22.03. 15:15" ou "16.12.2023 15:15"
                
                # Parse do kickoff com hora e minuto
                date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.(?:\s*(\d{4}))?\s+(\d{1,2}):(\d{1,2})', date_text)
                if date_match:
                    day = int(date_match.group(1))
                    month = int(date_match.group(2))
                    explicit_year_str = date_match.group(3)
                    hour = int(date_match.group(4))
                    minute = int(date_match.group(5))
                    
                    match_year = int(explicit_year_str) if explicit_year_str else recent_year
                    
                    from zoneinfo import ZoneInfo
                    sp_tz = ZoneInfo("America/Sao_Paulo")
                    kickoff_dt = datetime(match_year, month, day, hour, minute, tzinfo=sp_tz)
                else:
                    # Fallback para date-only
                    date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.\s*(\d{4})?', date_text)
                    if date_match:
                        day = int(date_match.group(1))
                        month = int(date_match.group(2))
                        explicit_year_str = date_match.group(3)
                        match_year = int(explicit_year_str) if explicit_year_str else recent_year
                        
                        from zoneinfo import ZoneInfo
                        sp_tz = ZoneInfo("America/Sao_Paulo")
                        kickoff_dt = datetime(match_year, month, day, 12, 0, tzinfo=sp_tz)
                    else:
                        continue
                
                home_id = await get_or_create_team(home_team)
                away_id = await get_or_create_team(away_team)
                
                if not home_id or not away_id:
                    continue
                
                # Parse dos placares
                ft_home = ft_away = ht_home = ht_away = None
                status = 'scheduled'
                
                if mode == "results" or "results" in url:
                    status = 'finished'
                    score_home_node = match_div.find(class_=re.compile("event__score--home"))
                    score_away_node = match_div.find(class_=re.compile("event__score--away"))
                    if score_home_node and score_away_node:
                        try:
                            ft_home = int(score_home_node.get_text(strip=True))
                            ft_away = int(score_away_node.get_text(strip=True))
                        except ValueError:
                            pass
                            
                    part_node = match_div.find("div", class_="event__part")
                    if part_node:
                        part_text = part_node.get_text(strip=True)
                        m = re.search(r'\((\d+):(\d+)\)', part_text)
                        if m:
                            try:
                                ht_home = int(m.group(1))
                                ht_away = int(m.group(2))
                            except ValueError:
                                pass
                
                # Verifica se a partida já existe na base por time + data
                row = await conn.fetchrow("""
                    SELECT match_id, status, ft_home, ft_away, ht_home, ht_away, flashscore_id
                    FROM matches
                    WHERE league_id = $1
                      AND home_team_id = $2
                      AND away_team_id = $3
                      AND ABS(kickoff::date - $4::date) <= 1
                    LIMIT 1
                """, league_id, home_id, away_id, kickoff_dt.date())
                
                if row:
                    match_uuid = row["match_id"]
                    current_status = row["status"]
                    current_fs_id = row["flashscore_id"]
                    
                    if current_status == 'scheduled' and status == 'finished':
                        await conn.execute("""
                            UPDATE matches
                            SET status = 'finished',
                                ft_home = $1, ft_away = $2,
                                ht_home = $3, ht_away = $4,
                                flashscore_id = COALESCE(flashscore_id, $5),
                                scraping_flashscore = FALSE,
                                updated_at = NOW()
                            WHERE match_id = $6
                        """, ft_home, ft_away, ht_home, ht_away, fs_id, match_uuid)
                        updated_count += 1
                        print(f"  --> ATUALIZADO: {home_team} vs {away_team} atualizado para finalizado (fs_id={fs_id})")
                    else:
                        if current_fs_id != fs_id:
                            await conn.execute("""
                                UPDATE matches
                                SET flashscore_id = $1,
                                    updated_at = NOW()
                                WHERE match_id = $2
                            """, fs_id, match_uuid)
                            updated_count += 1
                            print(f"  --> ASSOCIADO: {home_team} vs {away_team} associado (fs_id={fs_id})")
                else:
                    # Inserção de partida para ligas primárias
                    if primary_source == 'flashscore':
                        await conn.execute("""
                            INSERT INTO matches (
                                season_id, league_id, home_team_id, away_team_id,
                                kickoff, status, ft_home, ft_away, ht_home, ht_away,
                                flashscore_id, scraping_flashscore, updated_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, FALSE, NOW())
                        """, season_id, league_id, home_id, away_id, kickoff_dt, status, ft_home, ft_away, ht_home, ht_away, fs_id)
                        updated_count += 1
                        print(f"  --> INSERIDO: {home_team} vs {away_team} criado como {status} (fs_id={fs_id})")
                        
            except Exception as e:
                print(f"[FlashscoreDiscovery] Falha num HTML match node: {e}")
                
        return updated_count

    async def collect(self, mode: str = "results", specific_leagues: List[str] = None, target_urls: Dict[str, List[str]] = None, **kwargs) -> CollectResult:
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
                context = await browser.new_context(
                    timezone_id="America/Sao_Paulo",
                    locale="pt-BR"
                )
                page = await context.new_page()
                
                url_counter = 0

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
                        url_counter += 1
                        print(f"\n[Flashscore] [{url_counter}] Discovery URL alvo: {url}")

                        try:
                            # Determina o season_id correspondente
                            league_id = await conn.fetchval("SELECT league_id FROM leagues WHERE code = $1", league_code)
                            if not league_id:
                                continue
                            
                            season_id = None
                            m_slug = re.search(r'-(\d{4}-\d{4}|\d{4})/results/?$', url)
                            if m_slug:
                                slug = m_slug.group(1)
                                label = slug.replace("-", "/")
                                season_id = await conn.fetchval(
                                    "SELECT season_id FROM seasons WHERE league_id = $1 AND label = $2",
                                    league_id, label
                                )
                            if not season_id:
                                season_id = await conn.fetchval(
                                    "SELECT season_id FROM seasons WHERE league_id = $1 AND is_current = TRUE",
                                    league_id
                                )

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
                            upd = await self._extract_matches_from_page(html, league_code, conn, url, season_id, mode)
                            total_updated += upd
                            print(f"[Flashscore] {league_code}: {upd} novos flashscore_ids atualizados na base de dados.\n")

                            await asyncio.sleep(2)

                        except Exception as e:
                            logger.error(f"[Flashscore] Falha no discovery para {league_code} ({url}): {e}")
                            errors.append(str(e))
                        
                await page.close()
                await context.close()
                

        from src.normalizer.team_resolver import TeamResolver
        flushed = await TeamResolver.flush_unknowns()
        if flushed > 0:
            logger.info("flashscore_discovery_flushed_unknowns", count=flushed)

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
