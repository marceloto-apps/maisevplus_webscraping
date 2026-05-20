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

    async def _navigate_to_market_tab(self, page, market_href, period_slug=None, max_retries=0):
        """Navega para uma aba de mercado com retry."""
        for attempt in range(max_retries + 1):
            try:
                # 1. Clicar na aba do mercado usando JS evaluate
                clicked_market = await page.evaluate('''async (slug) => {
                    let keywords = {
                        "1x2-odds": ["1X2"],
                        "over-under": ["OVER", "UNDER", "ACIMA", "ABAIXO", "MÁS", "MAS", "MENOS", "ÜBER", "UNTER", "PLUS", "MOINS"],
                        "asian-handicap": ["ASIAN", "ASIÁTICO", "ASIATICO", "ASIATIQUE", "ASIATISCHES"],
                        "both-teams-to-score": ["BOTH", "BTTS", "AMBAS", "AMBOS", "BEIDE", "DEUX", "SQUADRE"],
                        "double-chance": ["DOUBLE", "DUPLA", "DOBLE", "DOPPELTE", "DOPPIA"],
                        "draw-no-bet": ["DRAW NO", "DNB", "ANULA", "VÁLIDA", "VALIDA", "UNENTSCHIEDEN", "REMBOURSÉ", "RIMBORSO"]
                    }[slug] || [];
                    
                    let btn = Array.from(document.querySelectorAll('button[role="tab"], a[role="tab"], div[role="tab"]'))
                                .find(el => {
                                    let txt = (el.textContent || el.innerText || "").trim().toUpperCase();
                                    return keywords.some(k => txt.includes(k)) && txt.length < 30;
                                });
                    if (btn) {
                        btn.click();
                        return true;
                    }
                    return false;
                }''', market_href)
                
                if not clicked_market:
                    logger.debug(f"[Flashscore] Sub-aba '{market_href}' não encontrada/clicada no menu de odds de {page.url}. Pulando.")
                    return False
                
                await page.wait_for_timeout(300)
                
                # 2. Se houver period_slug, clicar no respectivo botão de período
                if period_slug and period_slug != "full-time":
                    clicked_period = await page.evaluate('''async (slug) => {
                        let keywords = {
                            "full-time": ["FULL", "REGULAMENTAR", "COMPLETO", "HAUPTZEIT"],
                            "1st-half": ["1ST", "1º", "1ER", "1.", "1/H"],
                            "2nd-half": ["2ND", "2º", "2E", "2.", "2/H"]
                        }[slug] || [];
                        
                        let btn = Array.from(document.querySelectorAll('button[role="tab"], a[role="tab"], div[role="tab"]'))
                                    .find(el => {
                                        let txt = (el.textContent || el.innerText || "").trim().toUpperCase();
                                        return keywords.some(k => txt.includes(k)) && txt.length < 30;
                                    });
                        if (btn) {
                            btn.click();
                            return true;
                        }
                        return false;
                    }''', period_slug)
                    
                    if clicked_period:
                        await page.wait_for_timeout(300)
                
                # Timeout reduzido de 12s para 3s na navegação SPA das sub-abas
                await page.wait_for_selector("div.ui-table__row, a.oddsCell__odd", timeout=3000)
                return True
                
            except Exception as e:
                if attempt < max_retries:
                    logger.info(f"[Flashscore] Retry navegação para {market_href} (tentativa {attempt + 1}) devido a: {e}")
                    await page.wait_for_timeout(500)
                else:
                    raise e
        return False

    async def collect_match(self, browser, conn, match_id_uuid: str, flashscore_id: str, is_closing: bool, job_id: str, metrics: CollectionMetrics, is_prematch: bool = False, kickoff: datetime = None, skip_stats: bool = False) -> dict:
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
        
        page = await browser.new_page()
        try:
            # 1. Navegar para a página-resumo da partida
            base_url = f"https://www.flashscore.com/match/{flashscore_id}/"
            logger.debug(f"[Flashscore] Navegando para {base_url}")
            
            try:
                await page.goto(base_url, wait_until="domcontentloaded", timeout=self.config.page_timeout_ms)
            except Exception as e:
                logger.warning(f"[Flashscore] Timeout na página base de {flashscore_id}: {e}")

            # 2. Coletar Estatísticas PRIMEIRO (se aplicável)
            if not is_prematch and not skip_stats:
                logger.info(f"[Flashscore] [STATS] Buscando estatísticas para {flashscore_id} na página principal")
                try:
                    # O banner de privacidade "I Accept" bloqueia o scroll e interações
                    try:
                        accept_btn = page.locator('button#onetrust-accept-btn-handler')
                        if await accept_btn.count() > 0:
                            await accept_btn.click(timeout=2000)
                    except Exception:
                        pass

                    # Aguardar as abas (tablist ou odds tab) renderizarem no DOM antes de buscar o botão
                    try:
                        await page.wait_for_selector("div[role='tablist'], a[href*='/odds/'], a[href*='/1x2-odds/']", timeout=15000)
                    except Exception as e:
                        logger.warning(f"[Flashscore] [STATS] Timeout aguardando abas renderizarem no DOM para {flashscore_id}: {e}")

                    # Clicar diretamente na aba Stats/Estatísticas na página principal
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
                        # Aguardar o container de stats usando seletores combinados e timeout de 15s (para VPS lenta)
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
                            
                            # Executar a busca de TODAS as linhas wcl-statistics e stat__row (fallback)
                            stats_extracted = await page.evaluate('''() => {
                                let results = {};
                                
                                // Estratégia 1: Test IDs (mais robusto)
                                let rows = document.querySelectorAll('[data-testid="wcl-statistics"]');
                                for (let row of rows) {
                                    let textContent = row.innerText || "";
                                    let parts = textContent.split('\\n').map(p => p.trim()).filter(p => p.length > 0);
                                    
                                    // Categoria possui texto e rejeita elementos puros como '25%' ou '(9/36)'
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
                                
                                // Estratégia 2: Classes clássicas ou ofuscadas (fallback)
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
                            
                            if not stats_extracted:
                                html_dump = await page.content()
                                logger.warning(f"[Flashscore] [STATS] Nenhum stat extraído para {flashscore_id}. DOM size: {len(html_dump)}")
                            else:
                                logger.info(f"[Flashscore] [STATS] DOM extraído ({len(stats_extracted)} items): {list(stats_extracted.keys())}")
                            
                            xg_home = xg_away = xgot_home = xgot_away = None
                            xa_home = xa_away = crosses_home = crosses_away = None
                            
                            def parse_dom_val(v):
                                if not v: return None
                                try: return float(str(v).replace('%', '').strip())
                                except: return None

                            for cat, vals in stats_extracted.items():
                                if "expected goals (xg)" in cat and "xgot" not in cat:
                                    xg_home = parse_dom_val(vals["home"])
                                    xg_away = parse_dom_val(vals["away"])
                                elif ("xgot" in cat or "goals on target (xgot)" in cat or "expected goals on target" in cat) and "faced" not in cat:
                                    xgot_home = parse_dom_val(vals["home"])
                                    xgot_away = parse_dom_val(vals["away"])
                                elif "expected assists" in cat or "(xa)" in cat:
                                    xa_home = parse_dom_val(vals["home"])
                                    xa_away = parse_dom_val(vals["away"])
                                elif "crosses" in cat or "cruzamentos" in cat:
                                    def parse_crosses(v):
                                        if not v: return None
                                        v_str = str(v)
                                        if '/' in v_str:
                                            return int(''.join(filter(str.isdigit, v_str.split('/')[-1])))
                                        return int(''.join(filter(str.isdigit, v_str)))
                                    crosses_home = parse_crosses(vals["home"])
                                    crosses_away = parse_crosses(vals["away"])
                                    
                            logger.info(f"[Flashscore] [STATS] Stats parsed: xG={xg_home}/{xg_away} xGOT={xgot_home}/{xgot_away} xA={xa_home}/{xa_away} Crosses={crosses_home}/{crosses_away}")
                            
                            if any(v is not None for v in [xg_home, xgot_home, xa_home, crosses_home]):
                                await conn.execute("""
                                    INSERT INTO match_stats (
                                        match_id, 
                                        xg_fs_home, xg_fs_away, 
                                        xgot_fs_home, xgot_fs_away,
                                        xa_fs_home, xa_fs_away,
                                        crosses_fs_home, crosses_fs_away,
                                        collected_at
                                    ) VALUES (
                                        $1, 
                                        $2, $3, $4, $5, $6, $7, $8, $9, NOW()
                                    )
                                    ON CONFLICT (match_id) DO UPDATE SET
                                        xg_fs_home = COALESCE(EXCLUDED.xg_fs_home, match_stats.xg_fs_home),
                                        xg_fs_away = COALESCE(EXCLUDED.xg_fs_away, match_stats.xg_fs_away),
                                        xgot_fs_home = COALESCE(EXCLUDED.xgot_fs_home, match_stats.xgot_fs_home),
                                        xgot_fs_away = COALESCE(EXCLUDED.xgot_fs_away, match_stats.xgot_fs_away),
                                        xa_fs_home = COALESCE(EXCLUDED.xa_fs_home, match_stats.xa_fs_home),
                                        xa_fs_away = COALESCE(EXCLUDED.xa_fs_away, match_stats.xa_fs_away),
                                        crosses_fs_home = COALESCE(EXCLUDED.crosses_fs_home, match_stats.crosses_fs_home),
                                        crosses_fs_away = COALESCE(EXCLUDED.crosses_fs_away, match_stats.crosses_fs_away),
                                        collected_at = NOW()
                                """, match_id_uuid, xg_home, xg_away, xgot_home, xgot_away, xa_home, xa_away, crosses_home, crosses_away)
                                logger.info(f"[Flashscore] [STATS] Estatísticas avançadas salvas com sucesso para {flashscore_id}")
                            else:
                                logger.info(f"[Flashscore] [STATS] Partida {flashscore_id} processou a página mas não encontrou xG/xGOT/xA/Crosses.")
                except Exception as e:
                    logger.error(f"[Flashscore] [STATS] Falha ao coletar/salvar estatísticas para {flashscore_id}: {e}")

            # 3. Agora, navegar e CLICAR na aba "ODDS" (navegação SPA)
            odds_tab = None
            try:
                await page.wait_for_selector("a[href*='/odds/'], a[href*='/1x2-odds/']", timeout=15000)
                odds_tab = await page.query_selector("a[href*='/odds/'], a[href*='/1x2-odds/']")
            except Exception:
                logger.warning(f"[Flashscore] Aba Odds não encontrada para {flashscore_id}")
                return {
                    "total_inserted": total_inserted,
                    "markets_collected": markets_collected,
                    "markets_failed": list(set(self.markets_to_scrape.keys()) - set(markets_collected)),
                    "is_complete": False,
                }
            
            if not odds_tab:
                logger.warning(f"[Flashscore] Aba Odds não encontrada para {flashscore_id}")
                return {
                    "total_inserted": total_inserted,
                    "markets_collected": markets_collected,
                    "markets_failed": list(set(self.markets_to_scrape.keys()) - set(markets_collected)),
                    "is_complete": False,
                }
            
            await odds_tab.click()
            logger.debug(f"[Flashscore] Cliquei na aba Odds de {flashscore_id}")
            
            # 4. Esperar a tabela de odds do primeiro mercado (1x2 FT) renderizar
            try:
                await page.wait_for_selector("div.ui-table__row", timeout=15000)
            except Exception:
                # Tenta seletor alternativo
                try:
                    await page.wait_for_selector("a.oddsCell__odd", timeout=5000)
                except Exception:
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
            for m_key, m_config in self.markets_to_scrape.items():
                logger.debug(f"[Flashscore] Coletando {m_key} para {flashscore_id}")
                
                try:
                    if not is_first_market:
                        market_parts = m_config["hash"].replace("#/odds-comparison/", "").split("/")
                        market_type_slug = market_parts[0] if market_parts else ""  # ex: "over-under"
                        period_slug = market_parts[1] if len(market_parts) > 1 else ""  # ex: "full-time"
                        
                        # Clicar na aba do tipo de mercado (ex: Over/Under, Asian Handicap, etc.)
                        navigated = await self._navigate_to_market_tab(page, market_type_slug, period_slug)
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
                            
                    if len(odds_entries) > 0:
                        markets_collected.append(m_key)
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
                    
        finally:
            await page.close()
        REQUIRED_MARKETS = {"1x2_ft", "ou_ft"}
        is_complete = REQUIRED_MARKETS.issubset(set(markets_collected))
        return {
            "total_inserted": total_inserted,
            "markets_collected": markets_collected,
            "markets_failed": markets_failed,
            "is_complete": is_complete,
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
                        result = await self.collect_match(browser, conn, m_uuid, fs_id, is_closing, job_id, metrics, is_prematch, kickoff)
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
                                    success_rate, alert_level, job_id
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                            ''', 
                            self.source_name, metrics.total_processed, metrics.with_odds,
                            metrics.bet365_found, metrics.pinnacle_found, metrics.avg_bookmakers,
                            metrics.unidentified_rows, list(metrics.unknown_bookmakers), metrics.parse_errors,
                            metrics.success_rate, alert_level, job_id)
                            logger.info(f"[Flashscore] HealthMetrics salvas: {metrics.success_rate:.1%} success rate | Level: {alert_level}")
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
