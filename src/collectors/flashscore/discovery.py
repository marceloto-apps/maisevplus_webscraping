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

    Estratégia (em ordem de prioridade, da mais específica à mais genérica):
      1. Tenta o span com classe wcl-name_* (CSS Module do novo layout — mais preciso).
         Este seletor evita duplicar o nome que também aparece no atributo alt da <img>.
      2. Tenta encontrar o elemento por classe genérica 'name' ou 'participantName'.
      3. Tenta o atributo alt da <img> de escudo do time (limpo e direto).
      4. Tenta o primeiro NavigableString direto do nó.
      5. Como último recurso, clona o nó, remove tags de metadados indesejados e extrai get_text().
    """
    # 1. Span com classe wcl-name_* — introduzido no novo layout (2025+)
    #    A classe usa CSS Modules com sufixo hash (ex: wcl-name_jjfMf), mas sempre começa com "wcl-name"
    name_el = node.find(lambda tag: tag.name == "span" and tag.get("class")
                        and any(c.startswith("wcl-name") for c in tag.get("class", [])))
    if name_el:
        raw = name_el.get_text(strip=True)
        if raw:
            return _TEAM_SUFFIX_RE.sub("", raw).strip()

    # 2. Span/div com classe genérica 'name' ou 'participantName' (legado)
    name_el = node.find(class_=re.compile(r'\bname\b|participantName', re.I))
    if name_el:
        raw = name_el.get_text(strip=True)
        if raw:
            return _TEAM_SUFFIX_RE.sub("", raw).strip()

    # 3. Atributo alt da <img> de escudo — geralmente contém o nome limpo do time
    img_el = node.find("img", attrs={"data-testid": "wcl-participantLogo"})
    if not img_el:
        img_el = node.find("img", alt=True)
    if img_el:
        alt = (img_el.get("alt") or "").strip()
        if alt:
            return _TEAM_SUFFIX_RE.sub("", alt).strip()

    from bs4 import NavigableString
    # 4. Primeiro NavigableString direto — geralmente é o nome puro do time no layout legado
    for child in node.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                return text

    # 5. Fallback: get_text() completo, mas antes clona e decompõe elementos indesejados
    #    (SVG com cartões vermelhos, <img>, <button>, etc.)
    import copy
    node_copy = copy.copy(node)
    for bad_tag in node_copy.find_all(['svg', 'button', 'script', 'style', 'img']):
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
                if not await more_btn.is_visible():
                    logger.debug("[FlashscoreDiscovery] Fim do scroll: Botão 'Mostrar mais' está invisível.")
                    break
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
            tid = await TeamResolver.resolve("flashscore", name, league_code=league_code)
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

        match_divs = soup.find_all("div", id=re.compile(r"^g_1_"))
        if not match_divs:
            # Diagnóstico: loga um trecho do HTML para facilitar depuração de mudanças de layout
            body = soup.find("body")
            html_sample = str(body)[:800] if body else html[:800]
            logger.warning(
                f"[FlashscoreDiscovery] Nenhum nó 'div[id^=g_1_]' encontrado na página {url}. "
                f"HTML pode não ter renderizado (JS/anti-bot?). "
                f"Tamanho do HTML: {len(html)} bytes. Trecho: {html_sample[:200]!r}"
            )

        for match_div in match_divs:
            try:
                fs_id = match_div["id"].replace("g_1_", "")

                home_node = match_div.find("div", class_=re.compile("homeParticipant"))
                away_node = match_div.find("div", class_=re.compile("awayParticipant"))

                # Seletor de tempo: tenta classe semântica legada primeiro, depois data-testid moderno
                time_node = match_div.find(class_=re.compile(r"event__(stageTime|time)"))
                if not time_node:
                    time_node = match_div.find(attrs={"data-testid": "wcl-stageTime"})

                if not home_node or away_node is None or not time_node:
                    continue

                home_team = _extract_team_name(home_node)
                away_team = _extract_team_name(away_node)

                # Extração de data/hora: prefere o span interno com o conteúdo textual
                # (o span pai data-testid="wcl-stageTime" contém um span filho com o texto limpo)
                inner_time = time_node.find(attrs={"data-testid": "wcl-scores-simple-text-01"})
                date_text = (inner_time or time_node).get_text(strip=True)  # Ex: "22.03. 15:15"
                
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
                
                # Parse dos placares
                ft_home = ft_away = ht_home = ht_away = None
                status = 'scheduled'
                
                if mode == "results" or "results" in url:
                    status = 'finished'

                    # Placar FT: tenta classe semântica legada, depois data-testid + data-side modernos
                    score_home_node = match_div.find(class_=re.compile(r"event__score--home"))
                    score_away_node = match_div.find(class_=re.compile(r"event__score--away"))

                    # Fallback moderno: span[data-testid='wcl-tableScore'][data-side='home/away']
                    if not score_home_node:
                        score_home_node = match_div.find(
                            attrs={"data-testid": "wcl-tableScore", "data-side": "home"}
                        )
                    if not score_away_node:
                        score_away_node = match_div.find(
                            attrs={"data-testid": "wcl-tableScore", "data-side": "away"}
                        )

                    if score_home_node and score_away_node:
                        try:
                            ft_home = int(score_home_node.get_text(strip=True))
                            ft_away = int(score_away_node.get_text(strip=True))
                        except ValueError:
                            pass

                    # Placar HT: tenta div.event__part (legado)
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

                # 1. Buscar diretamente na base pelo flashscore_id (indexado e preciso)
                row = await conn.fetchrow("""
                    SELECT match_id, status, ft_home, ft_away, ht_home, ht_away, flashscore_id
                    FROM matches
                    WHERE flashscore_id = $1
                    LIMIT 1
                """, fs_id)
                
                if row:
                    match_uuid = row["match_id"]
                    current_status = row["status"]
                    
                    if current_status == 'scheduled' and status == 'finished':
                        await conn.execute("""
                            UPDATE matches
                            SET status = 'finished',
                                ft_home = $1, ft_away = $2,
                                ht_home = $3, ht_away = $4,
                                scraping_flashscore = FALSE,
                                updated_at = NOW()
                            WHERE match_id = $5
                        """, ft_home, ft_away, ht_home, ht_away, match_uuid)
                        updated_count += 1
                        print(f"  --> ATUALIZADO (via ID): {home_team} vs {away_team} atualizado para finalizado (fs_id={fs_id})")
                else:
                    # 2. Fallback: Se não encontrou por ID, resolve os times e faz a busca por time + data aproximada
                    home_id = await get_or_create_team(home_team)
                    away_id = await get_or_create_team(away_team)
                    
                    if not home_id or not away_id:
                        continue
                    
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
                            print(f"  --> ATUALIZADO (via times): {home_team} vs {away_team} atualizado para finalizado (fs_id={fs_id})")
                        else:
                            if current_fs_id != fs_id:
                                await conn.execute("""
                                    UPDATE matches
                                    SET flashscore_id = $1,
                                        updated_at = NOW()
                                    WHERE match_id = $2
                                """, fs_id, match_uuid)
                                updated_count += 1
                                print(f"  --> ASSOCIADO (via times): {home_team} vs {away_team} associado (fs_id={fs_id})")
                    else:
                        # 3. Inserção de nova partida (somente para ligas cuja fonte principal é o flashscore)
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

                            # Espera explícita pelo primeiro jogo renderizar (sinal que o JS principal rodou).
                            # Tenta seletor legado (div[id^="g_1_"]) e depois o novo link interno (a[id^="match-row-g_1_"]).
                            try:
                                await page.wait_for_selector(
                                    'div[id^="g_1_"], a[id^="match-row-g_1_"]',
                                    timeout=20000
                                )
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
