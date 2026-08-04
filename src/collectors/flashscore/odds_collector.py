import asyncio
from datetime import datetime, timezone
from typing import List, Dict
from bs4 import BeautifulSoup

from camoufox.async_api import AsyncCamoufox
from dataclasses import dataclass

from src.collectors.base import BaseCollector, CollectResult, CollectStatus
from src.collectors.flashscore.config import FlashscoreConfig, FLASHSCORE_BOOKMAKER_MAP
from src.collectors.flashscore.parser import FlashscoreParser
from src.normalizer.dedup import insert_odds_if_new
from src.normalizer.prematch_tracker import insert_prematch_odds
from src.db.pool import get_pool
from src.db.logger import get_logger

logger = get_logger(__name__)

@dataclass
class CollectionMetrics:
    total_processed: int = 0
    with_odds: int = 0
    bet365_found: int = 0
    pinnacle_found: int = 0
    unidentified_rows: int = 0
    unknown_bookmakers: set = None
    parse_errors: int = 0
    total_bookmakers_extracted: int = 0
    opening_found: int = 0  # partidas com ao menos 1 linha de opening inserida
    
    def __post_init__(self):
        if self.unknown_bookmakers is None:
            self.unknown_bookmakers = set()
            
    @property
    def avg_bookmakers(self) -> float:
        if self.total_processed == 0:
            return 0.0
        return self.total_bookmakers_extracted / self.total_processed
    
    @property
    def success_rate(self) -> float:
        if self.total_processed == 0:
            return 0.0
        return self.with_odds / self.total_processed
        
    def check_degradation(self) -> str:
        sr = self.success_rate
        if sr < 0.3 or self.bet365_found == 0:
            return '🔴'
        if sr < 0.5 or self.avg_bookmakers < 3:
            return '🟡'
        return '🟢'

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
                # Usamos lower() case-insensitive safety fallback
                self.bm_ids[row['name'].lower()] = row['bookmaker_id']
                self.bm_ids[row['name']] = row['bookmaker_id']

    async def _navigate_to_market_tab(self, page, market_href, period_slug=None, flashscore_id=None, max_retries=0):
        """Navega para uma aba de mercado com retry."""
        for attempt in range(max_retries + 1):
            try:
                # Helper para capturar o estado atual da tabela
                async def get_table_state():
                    return await page.evaluate('''() => {
                        let rows = Array.from(document.querySelectorAll('div.ui-table__row, [data-testid="wcl-tableRow"], [data-testid="wcl-oddsCell"], .oddsCell__odd'));
                        return rows.map(r => r.textContent.trim()).join('|');
                    }''')

                # Helper para aguardar a mudança das linhas da tabela
                async def wait_for_table_change(old_state):
                    start_time = asyncio.get_event_loop().time()
                    while asyncio.get_event_loop().time() - start_time < 2.0:
                        new_state = await get_table_state()
                        if new_state != old_state and new_state != "":
                            return True
                        if new_state == "" and old_state == "":
                            return True
                        await asyncio.sleep(0.05)
                    return False

                # 1. FASE 1: Navegar para o Mercado Correto (se necessário)
                already_on_market = market_href in page.url
                if not already_on_market:
                    old_state = await get_table_state()
                    
                    # Clicar na aba do mercado usando JS evaluate (priorizando href)
                    clicked_market = await page.evaluate('''async (market_slug) => {
                        // 1. Tentar por href (mais robusto e independente de idioma)
                        let link = document.querySelector(`a[href*="/odds/${market_slug}/"], a[href*="/${market_slug}/"]`);
                        if (link) {
                            link.click();
                            return true;
                        }
                        
                        // 2. Fallback por palavras-chave
                        let keywords = {
                            "1x2-odds": ["1X2"],
                            "over-under": ["OVER", "UNDER", "ACIMA", "ABAIXO", "MÁS", "MAS", "MENOS", "ÜBER", "UNTER", "PLUS", "MOINS", "O/U", "TOTAL", "GOALS", "GOLS"],
                            "asian-handicap": ["ASIAN", "ASIÁTICO", "ASIATICO", "ASIATIQUE", "ASIATISCHES", "AH", "HANDICAP"],
                            "both-teams-to-score": ["BOTH", "BTTS", "AMBAS", "AMBOS", "BEIDE", "DEUX", "SQUADRE"],
                            "double-chance": ["DOUBLE", "DUPLA", "DOBLE", "DOPPELTE", "DOPPIA", "DC"],
                            "draw-no-bet": ["DRAW NO", "DNB", "ANULA", "VÁLIDA", "VALIDA", "UNENTSCHIEDEN", "REMBOURSÉ", "RIMBORSO"]
                        }[market_slug] || [];
                        
                        let btn = Array.from(document.querySelectorAll('button, a, div[role="tab"], [data-testid*="tab"], a[href*="/odds/"]'))
                                    .find(el => {
                                        let txt = (el.textContent || el.innerText || "").trim().toUpperCase();
                                        return keywords.some(k => txt.includes(k)) && txt.length < 35;
                                    });
                        if (btn) {
                            btn.click();
                            return true;
                        }
                        return false;
                    }''', market_href)
                    
                    if not clicked_market:
                        # Fallback: tentar navegação direta via URL para a sub-aba do mercado
                        target_url = f"https://www.flashscore.com/match/{flashscore_id}/odds/{market_href}/full-time/"
                        logger.debug(f"[Flashscore] Sub-aba '{market_href}' não clicada via SPA. Tentando navegação direta: {target_url}")
                        try:
                            await page.goto(target_url, wait_until="domcontentloaded", timeout=self.config.page_timeout_ms)
                        except Exception as e:
                            logger.debug(f"[Flashscore] Falha ao navegar diretamente para {market_href}: {e}")
                            return False

                    # 1.1. Aguardar a URL atualizar para conter o market_href
                    start_wait = asyncio.get_event_loop().time()
                    while market_href not in page.url and asyncio.get_event_loop().time() - start_wait < 3.0:
                        await asyncio.sleep(0.05)

                    # 1.2. Aguardar que o DOM das abas/links de período seja atualizado para o novo mercado
                    start_wait = asyncio.get_event_loop().time()
                    while asyncio.get_event_loop().time() - start_wait < 2.0:
                        has_new_market_links = await page.evaluate('''async (market_slug) => {
                            let links = Array.from(document.querySelectorAll('a[href*="/odds/"]'));
                            return links.some(link => {
                                let href = link.getAttribute('href') || '';
                                return href.includes('/' + market_slug + '/');
                            });
                        }''', market_href)
                        if has_new_market_links:
                            break
                        await asyncio.sleep(0.05)

                    # 1.3. Aguardar que as linhas da tabela atualizem para o novo mercado
                    await wait_for_table_change(old_state)

                # 2. FASE 2: Navegar para o Período Correto (se necessário)
                already_on_period = False
                if period_slug:
                    if period_slug in page.url:
                        already_on_period = True
                    elif period_slug == "full-time" and not ("1st-half" in page.url or "2nd-half" in page.url):
                        already_on_period = True

                if period_slug and not already_on_period:
                    old_state = await get_table_state()

                    clicked_period = await page.evaluate('''async ({market_slug, period_slug}) => {
                        // 1. Tentar por href contendo market e período (mais preciso)
                        let link = document.querySelector(`a[href*="/${market_slug}/${period_slug}/"]`);
                        if (!link) {
                            // Fallback para link contendo apenas o período
                            link = document.querySelector(`a[href*="/${period_slug}/"]`);
                        }
                        if (link) {
                            link.click();
                            return true;
                        }
                        
                        // 2. Fallback por palavras-chave
                        let keywords = {
                            "full-time": ["FULL", "REGULAMENTAR", "COMPLETO", "HAUPTZEIT", "REGULAR", "REGLEMENTAIRE", "RÉGLEMENTAIRE"],
                            "1st-half": ["1ST", "1º", "1ER", "1.", "1/H", "1ª"],
                            "2nd-half": ["2ND", "2º", "2E", "2.", "2/H", "2ª"]
                        }[period_slug] || [];
                        
                        let tabs = Array.from(document.querySelectorAll('button[role="tab"], a[role="tab"], div[role="tab"], a, button'))
                                        .filter(el => el.offsetWidth > 0 && el.offsetHeight > 0);
                        
                        let btn = tabs.find(el => {
                            let txt = (el.textContent || el.innerText || "").trim().toUpperCase();
                            if (period_slug === "full-time" && (txt.includes("HALF TIME") || txt.includes("INTERVALO") || txt.includes("DESCANSO") || txt.includes("FINAL"))) {
                                return false;
                            }
                            return keywords.some(k => txt.includes(k)) && txt.length < 30;
                        });
                        
                        if (btn) {
                            btn.click();
                            return true;
                        }
                        return false;
                    }''', {"market_slug": market_href, "period_slug": period_slug})
                    
                    if not clicked_period and period_slug != "full-time":
                        logger.debug(f"[Flashscore] Sub-aba de período '{period_slug}' não encontrada via href ou fallback para o mercado '{market_href}'. Pulando.")
                        return False
                    
                    if clicked_period:
                        # 2.1. Aguardar a URL atualizar para conter o period_slug
                        start_wait = asyncio.get_event_loop().time()
                        if period_slug == "full-time":
                            while ("1st-half" in page.url or "2nd-half" in page.url) and asyncio.get_event_loop().time() - start_wait < 3.0:
                                await asyncio.sleep(0.05)
                        else:
                            while period_slug not in page.url and asyncio.get_event_loop().time() - start_wait < 3.0:
                                await asyncio.sleep(0.05)

                        # 2.2. Aguardar que as linhas da tabela atualizem para o novo período
                        await wait_for_table_change(old_state)
                
                # Garantir que pelo menos uma linha da tabela de odds está visível/pronta
                try:
                    await page.wait_for_selector("div.wclOddsRow, [data-testid='wcl-oddsCell'], button.wcl-oddsCell, div.ui-table__row, a.oddsCell__odd, div[class*='odds']", timeout=3000)
                except Exception:
                    pass
                return True
                
            except Exception as e:
                if attempt < max_retries:
                    logger.info(f"[Flashscore] Retry navegação para {market_href} (tentativa {attempt + 1}) devido a: {e}")
                    await page.wait_for_timeout(500)
                else:
                    raise e
        return False

    async def collect_match(self, browser, conn, match_id_uuid: str, flashscore_id: str, is_closing: bool, job_id: str, metrics: CollectionMetrics, is_prematch: bool = False, kickoff: datetime = None, skip_stats: bool = False, skip_closing: bool = False) -> dict:
        """
        Para uma única partida, usa navegação SPA (cliques) para acessar a aba de odds e estatísticas.
        Primeiro coleta as odds (que é o mercado principal e mais importante) e
        depois navega de volta para a aba de estatísticas para colher dados avançados.
        """
        await self._init_bm_ids(conn)
        
        total_inserted = 0
        match_unique_bookmakers = set()
        now = datetime.now(timezone.utc)
        
        markets_collected = []
        markets_failed = []
        
        # Cria um contexto dedicado com timezone e locale garantidos
        context = await browser.new_context(
            timezone_id="America/Sao_Paulo",
            locale="pt-BR"
        )
        page = await context.new_page()
        try:
            # 1. Navegar para a página-resumo da partida
            base_url = f"https://www.flashscore.com/match/{flashscore_id}/"
            logger.debug(f"[Flashscore] Navegando para {base_url}")
            
            try:
                await page.goto(base_url, wait_until="domcontentloaded", timeout=self.config.page_timeout_ms)
            except Exception as e:
                logger.warning(f"[Flashscore] Timeout na página base de {flashscore_id}: {e}")

            try:
                accept_btn = page.locator('button#onetrust-accept-btn-handler')
                if await accept_btn.count() > 0:
                    await accept_btn.click()
                    logger.debug(f"[Flashscore] Consentimento de cookies aceito para {flashscore_id}")
                    await page.wait_for_timeout(500)
            except Exception:
                pass

            # Confirmação de idade (18+ / 25+ / "Eu tenho mais de 18 anos") para liberar a aba de ODDS no DOM
            try:
                age_btn = page.locator("button:has-text('Eu tenho mais de 18 anos'), button:has-text('18 anos'), button:has-text('18 AND OLDER'), button:has-text('18+'), button:has-text('SOU MAIOR'), a[href*='legal-age']")
                if await age_btn.count() > 0:
                    await age_btn.first.click()
                    logger.debug(f"[Flashscore] Confirmação de idade (18+) aceita para {flashscore_id}")
                    await page.wait_for_timeout(500)
            except Exception:
                pass

            # Extrair placares FT e HT da página de detalhes e atualizar na tabela matches
            try:
                # Aguardar o container do score carregar para garantir que os placares estão na DOM
                try:
                    await page.wait_for_selector('div.detailScore__wrapper', timeout=5000)
                except Exception:
                    pass

                ft_home = ft_away = ht_home = ht_away = None

                # 1. Extrair placar FT
                score_wrapper = page.locator("div.detailScore__wrapper")
                if await score_wrapper.count() > 0:
                    span_elements = score_wrapper.locator("span")
                    if await span_elements.count() >= 3:
                        ft_home_text = await span_elements.nth(0).inner_text()
                        ft_away_text = await span_elements.nth(2).inner_text()
                        if ft_home_text.strip().isdigit() and ft_away_text.strip().isdigit():
                            ft_home = int(ft_home_text.strip())
                            ft_away = int(ft_away_text.strip())

                # 2. Extrair placar HT do summary
                summary_headers = page.locator("div.wclHeaderSection--summary")
                header_count = await summary_headers.count()
                for i in range(header_count):
                    header = summary_headers.nth(i)
                    spans = header.locator("span")
                    if await spans.count() >= 2:
                        label = await spans.nth(0).inner_text()
                        score_val = await spans.nth(1).inner_text()

                        first_half_keywords = ["1st half", "1o tempo", "1º tempo", "1st_half", "1. halbzeit", "1er temps", "1. tempo", "1 tempo", "1st"]
                        if any(k in label.lower() for k in first_half_keywords):
                            parts = score_val.split("-")
                            if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                                ht_home = int(parts[0].strip())
                                ht_away = int(parts[1].strip())
                                break
                            parts_colon = score_val.split(":")
                            if len(parts_colon) == 2 and parts_colon[0].strip().isdigit() and parts_colon[1].strip().isdigit():
                                ht_home = int(parts_colon[0].strip())
                                ht_away = int(parts_colon[1].strip())
                                break

                # Atualizar a tabela matches com os placares obtidos
                if ft_home is not None and ft_away is not None:
                    logger.info(f"[Flashscore] Atualizando placares no DB para {match_id_uuid}: FT={ft_home}-{ft_away}, HT={ht_home}-{ht_away}")
                    await conn.execute("""
                        UPDATE matches
                        SET ft_home = COALESCE($1, ft_home),
                            ft_away = COALESCE($2, ft_away),
                            ht_home = COALESCE($3, ht_home),
                            ht_away = COALESCE($4, ht_away),
                            updated_at = NOW()
                        WHERE match_id = $5
                    """, ft_home, ft_away, ht_home, ht_away, match_id_uuid)
            except Exception as e:
                logger.error(f"[Flashscore] Falha ao extrair/atualizar placares da página de detalhes: {e}")

            # Helper para navegar entre os sub-filtros de período das estatísticas
            async def _navigate_to_stats_period(p_slug: str) -> bool:
                async def get_stats_state():
                    return await page.evaluate('''() => {
                        let rows = Array.from(document.querySelectorAll('[data-testid="wcl-statistics"], .stat__row, div._row_96r0d_9, .statCategory'));
                        return rows.map(r => r.textContent.trim()).join('|');
                    }''')
                
                old_state = await get_stats_state()
                clicked = await page.evaluate('''async (p) => {
                    let keywords = {
                        "ft": ['MATCH', 'JOGO', 'ALL', 'TODO EL', 'SPIEL', 'TODOS'],
                        "ht": ['1ST HALF', '1º TEMPO', '1ST_HALF', '1. HALBZEIT', '1ER TEMPS', '1. TEMPO', '1 TEMPO', '1ST'],
                        "2h": ['2ND HALF', '2º TEMPO', '2ND_HALF', '2. HALBZEIT', '2E TEMPS', '2. TEMPO', '2 TEMPO', '2ND']
                    }[p];
                    
                    let btn = Array.from(document.querySelectorAll('a, button, div[role="tab"]'))
                        .find(el => {
                            let txt = (el.textContent || el.innerText || "").trim().toUpperCase();
                            return keywords.some(k => txt.includes(k)) && txt.length < 30;
                        });
                        
                    if (btn) {
                        btn.click();
                        return true;
                    }
                    return false;
                }''', p_slug)
                
                if clicked:
                    start_wait = asyncio.get_event_loop().time()
                    while asyncio.get_event_loop().time() - start_wait < 3.0:
                        new_state = await get_stats_state()
                        if new_state != old_state and new_state != "":
                            return True
                        await asyncio.sleep(0.1)
                    return True
                return False

            # 2. Coletar Estatísticas PRIMEIRO (se aplicável)
            if not is_prematch and not skip_stats:
                logger.info(f"[Flashscore] [STATS] Buscando estatísticas para {flashscore_id} na página principal")
                try:
                    # Aguardar as abas (tablist ou odds tab) renderizarem no DOM
                    try:
                        await page.wait_for_selector("div[role='tablist'], a[href*='/odds/'], a[href*='/1x2-odds/']", timeout=15000)
                    except Exception as e:
                        logger.warning(f"[Flashscore] [STATS] Timeout aguardando abas renderizarem no DOM para {flashscore_id}: {e}")

                    # Clicar diretamente na aba Stats/Estatísticas
                    stats_clicked = await page.evaluate('''() => {
                        let ot = document.getElementById('onetrust-consent-sdk');
                        if (ot) ot.style.display = 'none';
                        
                        let getButton = (names) => {
                            return Array.from(document.querySelectorAll('button, a, div[role="tab"]'))
                                        .find(el => {
                                            let txt = (el.textContent || el.innerText || "").trim().toUpperCase();
                                            return names.some(name => txt.includes(name)) && txt.length < 20;
                                        });
                        };
                        let statsBtn = getButton(['STAT', 'ESTAD']);
                        if (statsBtn) {
                            statsBtn.click();
                            return true;
                        }
                        return false;
                    }''')
                    
                    if not stats_clicked:
                        logger.warning(f"[Flashscore] [STATS] Botão de stats não encontrado no DOM SPA de {flashscore_id}")
                    else:
                        stats_selector = '[data-testid="wcl-statistics"], .stat__row, div._row_96r0d_9, .statCategory'
                        try:
                            await page.wait_for_selector(stats_selector, timeout=15000)
                            stats_loaded = True
                        except Exception:
                            stats_loaded = False
                        
                        if not stats_loaded:
                            logger.warning(f"[Flashscore] [STATS] Partida {flashscore_id} não possui container de estatísticas detectável. Pulando stats.")
                        else:
                            # Scroll-down para carregar as estatísticas adicionais
                            await page.evaluate('''async () => {
                                let ot = document.getElementById('onetrust-consent-sdk');
                                if(ot) ot.style.display = 'none';

                                for(let i=0; i<5; i++) {
                                    window.scrollBy({ top: window.innerHeight * 0.8, behavior: 'smooth' });
                                    await new Promise(r => setTimeout(r, 100));
                                }
                            }''')
                            
                            stats_data = {
                                "xg_home_ft": None, "xg_away_ft": None,
                                "xg_home_ht": None, "xg_away_ht": None,
                                "xg_home_2h": None, "xg_away_2h": None,
                                "xgot_home_ft": None, "xgot_away_ft": None,
                                "xgot_home_ht": None, "xgot_away_ht": None,
                                "xgot_home_2h": None, "xgot_away_2h": None,
                                "xa_home_ft": None, "xa_away_ft": None,
                                "xa_home_ht": None, "xa_away_ht": None,
                                "xa_home_2h": None, "xa_away_2h": None,
                            }
                            
                            for period in ["ft", "ht", "2h"]:
                                if period != "ft":
                                    navigated = await _navigate_to_stats_period(period)
                                    if not navigated:
                                        logger.debug(f"[Flashscore] [STATS] Não conseguiu navegar para período {period} de {flashscore_id}")
                                        continue
                                
                                stats_extracted = await page.evaluate('''() => {
                                    let results = {};
                                    let rows = document.querySelectorAll('[data-testid="wcl-statistics"]');
                                    for (let row of rows) {
                                        let textContent = row.innerText || "";
                                        let parts = textContent.split('\\n').map(p => p.trim()).filter(p => p.length > 0);
                                        let category = parts.find(p => /[A-Za-z]/.test(p) && !p.match(/^[\\d\\s/%()]+$/));
                                        if (!category) category = parts.find(p => /[A-Za-z]/.test(p));
                                        
                                        if (category) {
                                            let catIdx = parts.indexOf(category);
                                            if (catIdx > 0 && catIdx < parts.length - 1) {
                                                let home = parts.slice(0, catIdx).join(' ');
                                                let away = parts.slice(catIdx + 1).join(' ');
                                                results[category.toLowerCase()] = { "home": home, "away": away };
                                            }
                                        }
                                    }
                                    
                                    if (Object.keys(results).length === 0) {
                                        let statRows = document.querySelectorAll('.stat__row, div[class*="row_"]');
                                        for (let row of statRows) {
                                            let texts = Array.from(row.querySelectorAll('div, span'))
                                                            .map(el => el.innerText?.trim())
                                                            .filter(t => t && t.length > 0);
                                            if (texts.length >= 3) {
                                                let category = texts.find(t => /[A-Za-z]{3,}/.test(t));
                                                if (category) {
                                                    let catIdx = texts.indexOf(category);
                                                    if (catIdx > 0 && catIdx < texts.length - 1) {
                                                        results[category.toLowerCase()] = { 
                                                            "home": texts[catIdx - 1], 
                                                            "away": texts[catIdx + 1] 
                                                        };
                                                    }
                                                }
                                            }
                                            let cat = row.querySelector('.stat__categoryName')?.innerText || "";
                                            let hVal = row.querySelector('.stat__homeValue')?.innerText || "";
                                            let aVal = row.querySelector('.stat__awayValue')?.innerText || "";
                                            if (cat && hVal && aVal) {
                                                results[cat.toLowerCase()] = { "home": hVal, "away": aVal };
                                            }
                                        }
                                    }
                                    return results;
                                }''')
                                
                                if stats_extracted:
                                    def parse_dom_val(v):
                                        if not v: return None
                                        try: return float(str(v).replace('%', '').strip())
                                        except: return None
                                    
                                    for cat, vals in stats_extracted.items():
                                        if "expected goals (xg)" in cat and "xgot" not in cat:
                                            stats_data[f"xg_home_{period}"] = parse_dom_val(vals["home"])
                                            stats_data[f"xg_away_{period}"] = parse_dom_val(vals["away"])
                                        elif ("xgot" in cat or "goals on target (xgot)" in cat or "expected goals on target" in cat) and "faced" not in cat:
                                            stats_data[f"xgot_home_{period}"] = parse_dom_val(vals["home"])
                                            stats_data[f"xgot_away_{period}"] = parse_dom_val(vals["away"])
                                        elif "expected assists" in cat or "(xa)" in cat:
                                            stats_data[f"xa_home_{period}"] = parse_dom_val(vals["home"])
                                            stats_data[f"xa_away_{period}"] = parse_dom_val(vals["away"])
                                            
                            logger.info(f"[Flashscore] [STATS] Parsed stats para {flashscore_id}: {stats_data}")
                            
                            if any(v is not None for v in stats_data.values()):
                                await conn.execute("""
                                    INSERT INTO match_stats_fs (
                                        match_id, 
                                        xg_home_ft, xg_away_ft, 
                                        xg_home_ht, xg_away_ht, 
                                        xg_home_2h, xg_away_2h,
                                        xgot_home_ft, xgot_away_ft, 
                                        xgot_home_ht, xgot_away_ht, 
                                        xgot_home_2h, xgot_away_2h,
                                        xa_home_ft, xa_away_ft, 
                                        xa_home_ht, xa_away_ht, 
                                        xa_home_2h, xa_away_2h,
                                        collected_at, updated_at
                                    ) VALUES (
                                        $1, 
                                        $2, $3, $4, $5, $6, $7, 
                                        $8, $9, $10, $11, $12, $13, 
                                        $14, $15, $16, $17, $18, $19, 
                                        NOW(), NOW()
                                    )
                                    ON CONFLICT (match_id) DO UPDATE SET
                                        xg_home_ft = COALESCE(EXCLUDED.xg_home_ft, match_stats_fs.xg_home_ft),
                                        xg_away_ft = COALESCE(EXCLUDED.xg_away_ft, match_stats_fs.xg_away_ft),
                                        xg_home_ht = COALESCE(EXCLUDED.xg_home_ht, match_stats_fs.xg_home_ht),
                                        xg_away_ht = COALESCE(EXCLUDED.xg_away_ht, match_stats_fs.xg_away_ht),
                                        xg_home_2h = COALESCE(EXCLUDED.xg_home_2h, match_stats_fs.xg_home_2h),
                                        xg_away_2h = COALESCE(EXCLUDED.xg_away_2h, match_stats_fs.xg_away_2h),
                                        xgot_home_ft = COALESCE(EXCLUDED.xgot_home_ft, match_stats_fs.xgot_home_ft),
                                        xgot_away_ft = COALESCE(EXCLUDED.xgot_away_ft, match_stats_fs.xgot_away_ft),
                                        xgot_home_ht = COALESCE(EXCLUDED.xgot_home_ht, match_stats_fs.xgot_home_ht),
                                        xgot_away_ht = COALESCE(EXCLUDED.xgot_away_ht, match_stats_fs.xgot_away_ht),
                                        xgot_home_2h = COALESCE(EXCLUDED.xgot_home_2h, match_stats_fs.xgot_home_2h),
                                        xgot_away_2h = COALESCE(EXCLUDED.xgot_away_2h, match_stats_fs.xgot_away_2h),
                                        xa_home_ft = COALESCE(EXCLUDED.xa_home_ft, match_stats_fs.xa_home_ft),
                                        xa_away_ft = COALESCE(EXCLUDED.xa_away_ft, match_stats_fs.xa_away_ft),
                                        xa_home_ht = COALESCE(EXCLUDED.xa_home_ht, match_stats_fs.xa_home_ht),
                                        xa_away_ht = COALESCE(EXCLUDED.xa_away_ht, match_stats_fs.xa_away_ht),
                                        xa_home_2h = COALESCE(EXCLUDED.xa_home_2h, match_stats_fs.xa_home_2h),
                                        xa_away_2h = COALESCE(EXCLUDED.xa_away_2h, match_stats_fs.xa_away_2h),
                                        updated_at = NOW()
                                """, match_id_uuid,
                                    stats_data["xg_home_ft"], stats_data["xg_away_ft"],
                                    stats_data["xg_home_ht"], stats_data["xg_away_ht"],
                                    stats_data["xg_home_2h"], stats_data["xg_away_2h"],
                                    stats_data["xgot_home_ft"], stats_data["xgot_away_ft"],
                                    stats_data["xgot_home_ht"], stats_data["xgot_away_ht"],
                                    stats_data["xgot_home_2h"], stats_data["xgot_away_2h"],
                                    stats_data["xa_home_ft"], stats_data["xa_away_ft"],
                                    stats_data["xa_home_ht"], stats_data["xa_away_ht"],
                                    stats_data["xa_home_2h"], stats_data["xa_away_2h"]
                                )
                                logger.info(f"[Flashscore] [STATS] Estatísticas salvas no banco para {flashscore_id}")
                                await conn.execute("UPDATE matches SET flashscore_stats_collected = TRUE WHERE match_id = $1", match_id_uuid)
                            else:
                                logger.info(f"[Flashscore] [STATS] Partida {flashscore_id} processou a página mas não encontrou xG/xGOT/xA.")
                except Exception as e:
                    logger.error(f"[Flashscore] [STATS] Falha ao coletar/salvar estatísticas para {flashscore_id}: {e}")

            # 3. Navegar para a aba de odds (1x2 FT)
            # Se viemos da coleta de estatísticas (URL contém /stats/, /summary/, etc.), navegamos direto para a URL limpa de odds
            curr_url = page.url
            odds_clicked = False

            if any(sub in curr_url for sub in ['/stats/', '/summary/', '/report/', '/h2h/', '/standings/']):
                odds_url = f"https://www.flashscore.com/match/{flashscore_id}/#/odds-comparison/1x2-odds/full-time"
                logger.debug(f"[Flashscore] Transição de stats para odds de {flashscore_id}. Navegando para {odds_url}")
                try:
                    await page.goto(odds_url, wait_until="domcontentloaded", timeout=self.config.page_timeout_ms)
                    await page.wait_for_timeout(1500)
                    odds_clicked = True
                except Exception as e:
                    logger.warning(f"[Flashscore] Falha ao navegar direto para odds de {flashscore_id}: {e}")

            if not odds_clicked:
                # Garantir remoção do modal de idade caso tenha surgido durante a coleta de stats
                try:
                    age_btn = page.locator("button:has-text('Eu tenho mais de 18 anos'), button:has-text('18 anos'), button:has-text('18 AND OLDER'), button:has-text('18+'), button:has-text('SOU MAIOR'), a[href*='legal-age']")
                    if await age_btn.count() > 0:
                        await age_btn.first.click()
                        await page.wait_for_timeout(500)
                except Exception:
                    pass

                try:
                    await page.wait_for_selector("div[role='tablist'], a[href*='/odds/'], a[href*='/odds-comparison/'], a[href*='/1x2-odds/'], [data-testid*='odds']", timeout=5000)
                except Exception:
                    pass

                odds_clicked = await page.evaluate('''() => {
                    let ot = document.getElementById('onetrust-consent-sdk');
                    if (ot) ot.style.display = 'none';
                    
                    let els = Array.from(document.querySelectorAll('a, button, div[role="tab"]'));
                    let oddsLink = els.find(l => {
                        let href = (l.getAttribute('href') || '').toLowerCase();
                        let txt = (l.textContent || l.innerText || '').trim().toUpperCase();
                        if (href.includes('legal-age') || href.includes('version') || l.closest('footer')) return false;
                        return txt === 'ODDS' || txt === 'COTAÇÕES' || href.includes('/odds-comparison/') || href.includes('/odds/');
                    });
                    if (oddsLink) {
                        oddsLink.click();
                        return true;
                    }
                    return false;
                }''')

            if not odds_clicked:
                odds_url = f"https://www.flashscore.com/match/{flashscore_id}/#/odds-comparison/1x2-odds/full-time"
                logger.debug(f"[Flashscore] Botão ODDS não clicado via SPA. Fallback para {odds_url}")
                try:
                    await page.goto(odds_url, wait_until="domcontentloaded", timeout=self.config.page_timeout_ms)
                    await page.wait_for_timeout(1500)
                except Exception:
                    pass
            else:
                logger.debug(f"[Flashscore] Aba ODDS ativada com sucesso para {flashscore_id}")

            # 4. Aguardar tabela de odds — selector e polling do HTML
            odds_table_ready = False
            try:
                await page.wait_for_selector("div.wclOddsRow, div.ui-table__row, [data-testid='wcl-oddsCell'], button.wcl-oddsCell, a.oddsCell__odd", timeout=15000)
                await page.wait_for_timeout(2000)
                odds_table_ready = True
                logger.debug(f"[Flashscore] Tabela de odds carregou via selector para {flashscore_id}")
            except Exception:
                # Polling do HTML fonte
                logger.debug(f"[Flashscore] Selector timeout — polling HTML para {flashscore_id}")
                poll_start = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - poll_start < 10.0:
                    html_check = await page.content()
                    if any(x in html_check for x in ("ui-table__row", "wcl-tableRow", "wcl-oddsCell", "wcl-oddsValue", "oddsCell__odd", "oddsCell", "wcl-cell")):
                        odds_table_ready = True
                        logger.debug(f"[Flashscore] Tabela de odds encontrada via HTML poll para {flashscore_id}")
                        break
                    await asyncio.sleep(1.0)

            if not odds_table_ready:
                logger.warning(f"[Flashscore] Tabela de odds não renderizou para {flashscore_id}")
                return {
                    "total_inserted": total_inserted,
                    "markets_collected": markets_collected,
                    "markets_failed": list(set(self.markets_to_scrape.keys()) - set(markets_collected)),
                    "is_complete": False,
                }
            
            # 5. Iterar pelos mercados — o primeiro (1x2_ft) já está carregado após o clique na aba Odds.
            first_market_key = next(iter(self.markets_to_scrape), None)
            is_first_market = (first_market_key == "1x2_ft")
            match_opening_inserted = False  # flag por mercado para contabilizar opening_found
            for m_key, m_config in self.markets_to_scrape.items():
                logger.debug(f"[Flashscore] Coletando {m_key} para {flashscore_id}")
                
                try:
                    if not is_first_market:
                        market_parts = m_config["hash"].replace("#/odds-comparison/", "").split("/")
                        market_type_slug = market_parts[0] if market_parts else ""  # ex: "over-under"
                        period_slug = market_parts[1] if len(market_parts) > 1 else ""  # ex: "full-time"
                        
                        # Clicar na aba do tipo de mercado (ex: Over/Under, Asian Handicap, etc.)
                        navigated = await self._navigate_to_market_tab(page, market_type_slug, period_slug=period_slug, flashscore_id=flashscore_id)
                        if not navigated:
                            markets_failed.append(m_key)
                            continue
                    
                    is_first_market = False
                    
                    # Capturar HTML e parsear
                    html = await page.content()
                    try:
                        odds_entries, parsing_stats = FlashscoreParser.parse_odds_table(html, m_config, FLASHSCORE_BOOKMAKER_MAP)
                        logger.debug(f"[Flashscore] {m_key}: parsou {len(odds_entries)} linhas de odds")
                        metrics.unidentified_rows += parsing_stats["unidentified_rows"]
                        metrics.unknown_bookmakers.update(parsing_stats["unknown_bookmakers"])
                    except Exception as e:
                        logger.error(f"[Flashscore] Erro no parse_odds_table para {flashscore_id}: {e}")
                        metrics.parse_errors += 1
                        odds_entries = []
                    
                    for entry in odds_entries:
                        our_bm_key = entry["bookmaker"]
                        match_unique_bookmakers.add(our_bm_key)
                        bm_db_id = self.bm_ids.get(our_bm_key)
                        
                        if not bm_db_id:
                            logger.debug(f"[DEBUG-SKIP] Casa mapeada '{our_bm_key}' não achou ID correspondente no banco de dados!")
                            continue
                            
                        try:
                            if is_prematch:
                                is_new = await insert_prematch_odds(
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
                                    kickoff=kickoff,
                                    time=now
                                )
                            else:
                                # ── CLOSING (comportamento existente, inalterado) ──
                                is_new = False
                                if not skip_closing:
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
                            else:
                                logger.debug(f"[DEBUG-DEDUP] Odds ignoradas. Ja existem para {our_bm_key} / {entry['market_type']}")
                        except Exception as e:
                            logger.error(f"[DEBUG-INSERT] Falha crassa ao inserir: {e}")

                        # ── OPENING (linha adicional, isolada) ──
                        # Inserida SEMPRE após a closing, em try/except proprio.
                        # Qualquer falha aqui apenas é logada — nunca propaga
                        # nem faz rollback da closing já persistida.
                        # Não estão na mesma transação atômica: cada insert_odds_if_new
                        # executa seu próprio conn.execute() independente.
                        if not is_prematch:
                            opening_1 = entry.get("opening_1")
                            opening_x = entry.get("opening_x")
                            opening_2 = entry.get("opening_2")
                            # Só insere se ao menos um valor de abertura estiver presente
                            # (title sem '»' = odd não se moveu, Q1 = ignorar silenciosamente)
                            if any(v is not None for v in [opening_1, opening_x, opening_2]):
                                try:
                                    opening_inserted = await insert_odds_if_new(
                                        conn=conn,
                                        match_id=match_id_uuid,
                                        bookmaker_id=bm_db_id,
                                        market_type=entry["market_type"],
                                        line=entry["line"],
                                        period=entry["period"],
                                        odds_1=opening_1,
                                        odds_x=opening_x,
                                        odds_2=opening_2,
                                        source=self.source_name,
                                        collect_job_id=job_id,
                                        is_opening=True,
                                        is_closing=False,
                                        time=now,   # mesmo timestamp da closing (Q3)
                                    )
                                    if opening_inserted:
                                        match_opening_inserted = True
                                        total_inserted += 1
                                except Exception as e:
                                    logger.warning(
                                        f"[Flashscore] [OPENING] Falha ao inserir opening para "
                                        f"{our_bm_key}/{entry['market_type']}: {e} — closing não afetada."
                                    )
                            
                    if len(odds_entries) > 0:
                        markets_collected.append(m_key)
                        # Marca odds como coletadas no BD
                        await conn.execute("UPDATE matches SET flashscore_odds_collected = TRUE WHERE match_id = $1", match_id_uuid)
                        # Contabiliza opening se ao menos uma linha de abertura foi inserida neste mercado
                        if match_opening_inserted:
                            metrics.opening_found += 1
                            match_opening_inserted = False  # reset para o próximo mercado
                    else:
                        markets_failed.append(m_key)

                except Exception as e:
                    logger.warning(f"[Flashscore] Erro no mercado {m_key} para {flashscore_id}: {e}")
                    markets_failed.append(m_key)
                    is_first_market = False  # Garante progressão mesmo com erro
                    
            if 'bet365' in match_unique_bookmakers:
                metrics.bet365_found += 1
            if 'pinnacle' in match_unique_bookmakers:
                metrics.pinnacle_found += 1
            metrics.total_bookmakers_extracted += len(match_unique_bookmakers)
            
            # Capturar HTML de diagnóstico quando o parser não extraiu nenhuma odd
            debug_html = None
            if not markets_collected and total_inserted == 0:
                try:
                    debug_html = await page.content()
                    logger.debug(f"[Flashscore] HTML de diagnóstico capturado para {flashscore_id} ({len(debug_html)} bytes)")
                except Exception:
                    pass
                    
        finally:
            await page.close()
            await context.close()
        REQUIRED_MARKETS = {"1x2_ft", "ou_ft"}
        is_complete = REQUIRED_MARKETS.issubset(set(markets_collected))
        return {
            "total_inserted": total_inserted,
            "markets_collected": markets_collected,
            "markets_failed": markets_failed,
            "is_complete": is_complete,
            "debug_html": debug_html,
        }

    async def collect(self, match_ids: List[dict] = None, is_closing: bool = False, is_prematch: bool = False, **kwargs) -> CollectResult:
        """
        Ponto de entrada do BaseCollector.
        match_ids: lista de dicionários contendo {"match_id": UUID, "flashscore_id": str, "kickoff": datetime}
        is_closing: se True, marca as odds como is_closing = TRUE (útil para jogos pós match)
        is_prematch: se True, redireciona o fluxo para a tabela prematch_odds
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

        metrics = CollectionMetrics()
        
        pool = await get_pool()
        async with pool.acquire() as conn:
            await self._init_bm_ids(conn)
            
            logger.info(f"[Flashscore] Iniciando browser (Headless={self.config.headless}) para {len(match_ids)} matches")
            
            try:
                async with AsyncCamoufox(headless=self.config.headless, os="linux") as browser:
                    for idx, m in enumerate(match_ids):
                        m_uuid = m["match_id"]
                        fs_id = m.get("flashscore_id")
                        kickoff = m.get("kickoff")
                        
                        if not fs_id:
                            total_skipped += 1
                            continue
                            
                        metrics.total_processed += 1
                        logger.info(f"[Flashscore] Progresso: {idx+1}/{len(match_ids)} | Match: {fs_id}")
                        result = await self.collect_match(
                            browser, conn, m_uuid, fs_id, is_closing, job_id, metrics,
                            is_prematch, kickoff, skip_stats=kwargs.get("skip_stats", False)
                        )
                        inserted = result["total_inserted"]
                        
                        if inserted > 0:
                            metrics.with_odds += 1
                            
                        total_collected += 1  # Conta matches processados
                        total_new += inserted
                        # Respeitar rate limits / evitar bans parecendo scripts
                        await asyncio.sleep(2)
                        
                    # Ao final do loop, salva a saúde
                    if metrics.total_processed > 0:
                        alert_level = metrics.check_degradation()
                        try:
                            await conn.execute('''
                                INSERT INTO scraping_health (
                                    source, total_matches, matches_with_odds,
                                    bet365_found, pinnacle_found, avg_bookmakers,
                                    unidentified_rows, unknown_bookmakers, parse_errors,
                                    success_rate, alert_level, job_id, opening_found
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                            ''', 
                            self.source_name, metrics.total_processed, metrics.with_odds,
                            metrics.bet365_found, metrics.pinnacle_found, metrics.avg_bookmakers,
                            metrics.unidentified_rows, list(metrics.unknown_bookmakers), metrics.parse_errors,
                            metrics.success_rate, alert_level, job_id, metrics.opening_found)
                            logger.info(f"[Flashscore] HealthMetrics salvas: {metrics.success_rate:.1%} success rate | Level: {alert_level.replace('🔴', 'RED').replace('🟡', 'YELLOW').replace('🟢', 'GREEN')}")
                        except Exception as e:
                            logger.error(f"[Flashscore] Falha ao salvar scraping_health: {e}")
                            
                        if alert_level == '🔴':
                            logger.critical(f"DEGRADAÇÃO CRÍTICA DETECTADA: Taxa={metrics.success_rate:.1%}, bet365={metrics.bet365_found}")
                            raise SystemExit("CRITICAL: scraping degradado")
                        
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
