#!/usr/bin/env python3
import asyncio
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

# ============================================================
# CONFIGURAÇÃO
# ============================================================

BASE_URL = "https://www.betexplorer.com"
OUTPUT_DIR = Path("./output/discovery_samples")
REPORT_PATH = Path("./output/discovery_report.json")

# Rate limiting: 3s entre requests + jitter
REQUEST_DELAY = 3.0

# User agents rotativos
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
]

# Mapeamento das 26 ligas → slugs candidatos do BetExplorer
LEAGUE_SLUGS = {
    # Tier 1 — England
    "ENG_PL": ["england/premier-league"],
    "ENG_CH": ["england/championship"],
    "ENG_L1": ["england/league-one"],
    "ENG_L2": ["england/league-two"],
    "ENG_NL": ["england/national-league", "england/conference"],
    # Tier 1 — Scotland
    "SCO_PL": ["scotland/premiership"],
    "SCO_CH": ["scotland/championship"],
    "SCO_L1": ["scotland/league-one", "scotland/league-1"],
    "SCO_L2": ["scotland/league-two", "scotland/league-2"],
    # Tier 1 — Germany
    "GER_BL": ["germany/bundesliga"],
    "GER_B2": ["germany/2-bundesliga", "germany/bundesliga-2", "germany/2.-bundesliga"],
    # Tier 1 — Italy
    "ITA_SA": ["italy/serie-a"],
    "ITA_SB": ["italy/serie-b"],
    # Tier 1 — Spain
    "ESP_PD": ["spain/laliga", "spain/la-liga"],
    "ESP_SD": ["spain/laliga2", "spain/la-liga-2", "spain/segunda-division"],
    # Tier 1 — France
    "FRA_L1": ["france/ligue-1"],
    "FRA_L2": ["france/ligue-2"],
    # Tier 2
    "NED_ED": ["netherlands/eredivisie"],
    "BEL_PL": ["belgium/jupiler-pro-league", "belgium/first-division-a"],
    "POR_PL": ["portugal/primeira-liga", "portugal/liga-portugal"],
    "TUR_SL": ["turkey/super-lig", "turkey/super-league"],
    "GRE_SL": ["greece/super-league"],
    # Tier 3
    "BRA_SA": ["brazil/serie-a-betano", "brazil/serie-a"],
    "MEX_LM": ["mexico/liga-mx"],
    "AUT_BL": ["austria/bundesliga"],
    "SWI_SL": ["switzerland/super-league"],
}

# Mercados secundários — hash fragments a testar
MARKET_TABS = {
    "1x2":    "",                     # Default (sem hash)
    "ou":     "#/over-under",
    "ah":     "#/asian-handicap",
    "dc":     "#/double-chance",
    "dnb":    "#/draw-no-bet",
    "btts":   "#/both-teams-to-score",
    "1x2_ht": "#/1st-half",           # Candidatos para HT
    "ou_ht":  "#/over-under/1st-half",
    "ah_ht":  "#/asian-handicap/1st-half",
}

TEST_SEASONS = ["2025-2026", "2024-2025"]

# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class LeagueDiscovery:
    code: str
    slug_tested: list = field(default_factory=list)
    valid_slug: Optional[str] = None
    results_url: Optional[str] = None
    status_code: Optional[int] = None
    has_results_table: bool = False
    sample_match_count: int = 0
    sample_match_url: Optional[str] = None
    sample_match_id: Optional[str] = None
    error: Optional[str] = None

@dataclass
class MatchPageDiscovery:
    match_url: str
    league_code: str
    status_code: Optional[int] = None
    has_odds_table: bool = False
    bookmakers_found: list = field(default_factory=list)
    bookmaker_count: int = 0
    has_opening_odds: bool = False
    opening_odds_method: Optional[str] = None
    has_closing_odds: bool = False
    odds_sample: dict = field(default_factory=dict)
    error: Optional[str] = None

@dataclass
class MarketDiscovery:
    market: str
    hash_fragment: str
    ajax_endpoint_found: Optional[str] = None
    inline_data: bool = False
    needs_js_render: bool = False
    lines_found: list = field(default_factory=list)
    bookmakers_found: list = field(default_factory=list)
    error: Optional[str] = None

@dataclass
class DiscoveryReport:
    timestamp: str
    leagues: list = field(default_factory=list)
    match_pages: list = field(default_factory=list)
    markets: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)

# ============================================================
# CLIENT HTTP
# ============================================================

class BetExplorerClient:
    def __init__(self):
        self._agent_idx = 0
        self._request_count = 0

    def _get_headers(self) -> dict:
        agent = USER_AGENTS[self._agent_idx % len(USER_AGENTS)]
        self._agent_idx += 1
        return {
            "User-Agent": agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": f"{BASE_URL}/football/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def get(self, url: str, client: httpx.AsyncClient) -> tuple[int, str]:
        await asyncio.sleep(REQUEST_DELAY)
        self._request_count += 1
        try:
            resp = await client.get(url, headers=self._get_headers(), follow_redirects=True)
            return resp.status_code, resp.text
        except Exception as e:
            return 0, str(e)

# ============================================================
# FASE 1
# ============================================================

async def phase1_validate_leagues(http: BetExplorerClient, client: httpx.AsyncClient) -> list[LeagueDiscovery]:
    print("\n" + "=" * 60)
    print("FASE 1: Validação de URLs")
    print("=" * 60)
    results = []

    for code, slugs in LEAGUE_SLUGS.items():
        discovery = LeagueDiscovery(code=code)
        for slug in slugs:
            urls_to_try = [
                f"{BASE_URL}/football/{slug}/results/",
                f"{BASE_URL}/football/{slug}-{TEST_SEASONS[0]}/results/",
                f"{BASE_URL}/football/{slug}/",
            ]
            for url in urls_to_try:
                discovery.slug_tested.append(url)
                status, html = await http.get(url, client)

                if status == 200 and len(html) > 5000:
                    soup = BeautifulSoup(html, "html.parser")
                    tables = soup.find_all("table")
                    match_links = soup.find_all("a", href=re.compile(r"/football/.+/.+/.+-[a-zA-Z0-9]{6,}/?$"))

                    if match_links:
                        discovery.valid_slug = slug
                        discovery.results_url = url
                        discovery.status_code = status
                        discovery.has_results_table = len(tables) > 0
                        discovery.sample_match_count = len(match_links)

                        href = match_links[0].get("href", "")
                        if href:
                            discovery.sample_match_url = urljoin(BASE_URL, href)
                            match_id_match = re.search(r"/([a-zA-Z0-9]{6,12})/?$", href)
                            if match_id_match:
                                discovery.sample_match_id = match_id_match.group(1)

                        save_html(html, f"phase1_{code}_results.html")
                        print(f"  ✅ {code}: {slug} → {discovery.sample_match_count} jogos encontrados")
                        break

            if discovery.valid_slug:
                break

        if not discovery.valid_slug:
            discovery.error = f"Nenhum slug válido"
            print(f"  ❌ {code}: Nenhum slug funcionou")

        results.append(discovery)
    return results

# ============================================================
# FASE 2
# ============================================================

async def phase2_parse_results_page(http: BetExplorerClient, client: httpx.AsyncClient, leagues: list[LeagueDiscovery]) -> list[LeagueDiscovery]:
    print("\n" + "=" * 60)
    print("FASE 2: Parse de página de resultados")
    print("=" * 60)

    test_leagues = [lg for lg in leagues if lg.valid_slug][:3]
    for league in test_leagues:
        status, html = await http.get(league.results_url, client)
        if status != 200: continue

        soup = BeautifulSoup(html, "html.parser")
        odds_elements = soup.find_all(attrs={"data-odd": True})
        
        print(f"\n  📊 {league.code} ({league.results_url}):")
        print(f"     data-odd attrs: {len(odds_elements)}")
        save_html(html, f"phase2_{league.code}_results_full.html")

    return leagues

# ============================================================
# FASE 3
# ============================================================

async def phase3_parse_match_page(http: BetExplorerClient, client: httpx.AsyncClient, leagues: list[LeagueDiscovery]) -> list[MatchPageDiscovery]:
    print("\n" + "=" * 60)
    print("FASE 3: Parse página individual")
    print("=" * 60)
    match_results = []

    for league in leagues:
        if not league.sample_match_url: continue
        if len(match_results) >= 3: break

        url = league.sample_match_url
        status, html = await http.get(url, client)
        discovery = MatchPageDiscovery(match_url=url, league_code=league.code, status_code=status)

        if status != 200:
            discovery.error = f"HTTP {status}"
            match_results.append(discovery)
            continue

        soup = BeautifulSoup(html, "html.parser")
        known_bookmakers = ["Pinnacle", "bet365", "Bet365", "1xBet", "Betfair", "Betano"]
        
        html_lower = html.lower()
        for bk in known_bookmakers:
            if bk.lower() in html_lower:
                discovery.bookmakers_found.append(bk)
        discovery.bookmaker_count = len(discovery.bookmakers_found)

        data_odd_attrs = soup.find_all(attrs={"data-odd": True})
        if data_odd_attrs:
            discovery.has_opening_odds = True
            discovery.opening_odds_method = "data-odd-attr"

        dds_cells = soup.find_all("td", class_=re.compile(r"odds|table-main"))
        if dds_cells: discovery.has_closing_odds = True

        for td in data_odd_attrs[:9]:
            val = td.get("data-odd", "")
            if val: discovery.odds_sample[f"data_odd_{len(discovery.odds_sample)}"] = val

        print(f"\n  📊 {league.code} ({url}):")
        print(f"     Bookmakers: {discovery.bookmaker_count}")
        match_results.append(discovery)
        save_html(html, f"phase3_{league.code}_match.html")

    return match_results

# ============================================================
# FASE 4
# ============================================================

async def phase4_test_markets(http: BetExplorerClient, client: httpx.AsyncClient, match_pages: list[MatchPageDiscovery]) -> list[MarketDiscovery]:
    print("\n" + "=" * 60)
    print("FASE 4: Mercados secundários")
    print("=" * 60)
    market_results = []
    test_url = next((mp.match_url for mp in match_pages if mp.match_url and mp.status_code == 200), None)

    if not test_url: return market_results
    base_match_url = test_url.rstrip("/")

    for market, hash_frag in MARKET_TABS.items():
        discovery = MarketDiscovery(market=market, hash_fragment=hash_frag)
        if not hash_frag:
            discovery.inline_data = True
            market_results.append(discovery)
            continue

        match_id_match = re.search(r"/([a-zA-Z0-9]{6,12})/?$", base_match_url)
        match_id = match_id_match.group(1) if match_id_match else ""
        
        market_slug = hash_frag.replace("#/", "")
        ajax_candidates = [
            f"{base_match_url}/{market_slug}/",
            f"{BASE_URL}/match-odds/{match_id}/{market_slug}/",
            f"{BASE_URL}/gres/ajax-sport-country-tournament-event-ede_{match_id}.dat",
            f"{BASE_URL}/feed/match/{match_id}/{market_slug}/"
        ]

        print(f"\n  🔍 {market} ({hash_frag}):")
        for ajax_url in ajax_candidates:
            status, html = await http.get(ajax_url, client)
            if status == 200 and len(html) > 500:
                has_odds_pattern = bool(re.search(r"\d+\.\d{2}", html))
                if has_odds_pattern:
                    discovery.ajax_endpoint_found = ajax_url
                    soup = BeautifulSoup(html, "html.parser")
                    line_elements = soup.find_all(string=re.compile(r"[+-]?\d+\.\d{1,2}"))
                    if line_elements: discovery.lines_found = [el.strip() for el in line_elements[:10]]
                    print(f"     ✅ AJAX endpoint: {ajax_url}")
                    save_html(html, f"phase4_{market}_ajax.html")
                    break
        
        if not discovery.ajax_endpoint_found:
            discovery.needs_js_render = True
            print(f"     ⚠️ Provável JS render necessário.")
        
        market_results.append(discovery)

    return market_results

# ============================================================
# HELPERS & MAIN
# ============================================================

def save_html(html: str, filename: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / filename, "w", encoding="utf-8") as f:
        f.write(html)

def generate_summary(leagues, match_pages, markets):
    valid_leagues = [l for l in leagues if l.valid_slug]
    ajax_markets = [m for m in markets if m.ajax_endpoint_found]
    js_markets = [m for m in markets if m.needs_js_render]
    return {
        "valid_leagues": len(valid_leagues),
        "markets_via_ajax": [m.market for m in ajax_markets],
        "markets_need_js": [m.market for m in js_markets],
        "recommendation": "PLAYWRIGHT_REQUIRED" if js_markets else "HTTPX_ONLY"
    }

async def main():
    http = BetExplorerClient()
    async with httpx.AsyncClient(timeout=30.0, verify=True) as client:
        leagues = await phase1_validate_leagues(http, client)
        leagues = await phase2_parse_results_page(http, client, leagues)
        match_pages = await phase3_parse_match_page(http, client, leagues)
        markets = await phase4_test_markets(http, client, match_pages)

    summary = generate_summary(leagues, match_pages, markets)
    report = DiscoveryReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        leagues=[asdict(l) for l in leagues],
        match_pages=[asdict(m) for m in match_pages],
        markets=[asdict(m) for m in markets],
        summary=summary,
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2, ensure_ascii=False, default=str)
    
    print("\nRelatório gerado em", REPORT_PATH)

if __name__ == "__main__":
    asyncio.run(main())
