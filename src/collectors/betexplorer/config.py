"""
BetExplorer Collector — Configuração
"""
from dataclasses import dataclass, field

# ============================================================
# LEAGUE MAPPING
# ============================================================
LEAGUE_BETEXPLORER_PATHS: dict[str, str] = {
    "ENG_PL": "england/premier-league",
    "ENG_CH": "england/championship",
    "ENG_L1": "england/league-one",
    "ENG_L2": "england/league-two",
    "ENG_NL": "england/national-league",
    "SCO_PL": "scotland/premiership",
    "SCO_CH": "scotland/championship",
    "SCO_L1": "scotland/league-one",
    "SCO_L2": "scotland/league-two",
    "GER_BL": "germany/bundesliga",
    "GER_B2": "germany/2-bundesliga",
    "ITA_SA": "italy/serie-a",
    "ITA_SB": "italy/serie-b",
    "ESP_PD": "spain/laliga",
    "ESP_SD": "spain/laliga2",
    "FRA_L1": "france/ligue-1",
    "FRA_L2": "france/ligue-2",
    "NED_ED": "netherlands/eredivisie",
    "BEL_PL": "belgium/jupiler-pro-league",
    "POR_PL": "portugal/primeira-liga",
    "TUR_SL": "turkey/super-lig",
    "GRE_SL": "greece/super-league",
    "BRA_SA": "brazil/serie-a-betano",
    "MEX_LM": "mexico/liga-mx",
    "AUT_BL": "austria/bundesliga",
    "SWI_SL": "switzerland/super-league",
}

# ============================================================
# MARKET TABS (hash fragments para Playwright)
# ============================================================
MARKET_TABS: dict[str, dict] = {
    # Mercados FT — Todos precisam de Playwright pois as odds são injetadas no client-side
    "1x2_ft": {
        "engine": "playwright",
        "tab_selector": None,  # Default, sem click, apenas aguarda renderização
        "hash": "",
    },
    "ou_ft": {
        "engine": "playwright",
        "tab_selector": 'a[href*="over-under"], li:has-text("Over/Under")',
        "hash": "#/over-under",
    },
    "ah_ft": {
        "engine": "playwright",
        "tab_selector": 'a[href*="asian-handicap"], li:has-text("Asian Handicap")',
        "hash": "#/asian-handicap",
    },
    "dc_ft": {
        "engine": "playwright",
        "tab_selector": 'a[href*="double-chance"], li:has-text("Double Chance")',
        "hash": "#/double-chance",
    },
    "dnb_ft": {
        "engine": "playwright",
        "tab_selector": 'a[href*="draw-no-bet"], li:has-text("Draw No Bet")',
        "hash": "#/draw-no-bet",
    },
    "btts_ft": {
        "engine": "playwright",
        "tab_selector": 'a[href*="both-teams"], li:has-text("Both Teams")',
        "hash": "#/both-teams-to-score",
    },
    # Mercados HT — todos Playwright
    "1x2_ht": {
        "engine": "playwright",
        "tab_selector": 'a[href*="1st-half"], li:has-text("1st Half")',
        "hash": "#/1st-half",
    },
    "ou_ht": {
        "engine": "playwright",
        "tab_selector": None,  # Pode ser sub-tab dentro de OU
        "hash": "#/over-under/1st-half",
        "parent_tab": "ou_ft",
    },
    "ah_ht": {
        "engine": "playwright",
        "tab_selector": None,
        "hash": "#/asian-handicap/1st-half",
        "parent_tab": "ah_ft",
    },
}

# ============================================================
# RATE LIMITING
# ============================================================
@dataclass
class RateLimitConfig:
    # Engine A (httpx)
    http_delay_base: float = 3.0        # segundos entre requests
    http_delay_jitter: float = 1.5      # random(0, jitter)
    http_max_per_minute: int = 15
    http_retry_on_429: list = field(default_factory=lambda: [30, 60, 120])

    # Engine B (Playwright)
    browser_tab_delay: float = 2.0      # entre clicks de tab
    browser_page_delay: float = 4.0     # entre jogos diferentes
    browser_wait_after_click: float = 2.5  # espera renderização da tab
    browser_max_pages_per_session: int = 50  # reinicia browser a cada N

    # Geral
    max_concurrent_http: int = 3
    max_concurrent_browser: int = 1


USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
]

BASE_URL = "https://www.betexplorer.com"
