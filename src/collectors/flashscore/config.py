import os
from dataclasses import dataclass, field
from typing import Dict, Optional

# Mapeamento do código interno da liga para o path do Flashscore
# Usado para compor as URLs de fixtures e results
LEAGUE_FLASHSCORE_PATHS: Dict[str, str] = {
    "ENG_PL": "football/england/premier-league",
    "ENG_CH": "football/england/championship",
    "ENG_L1": "football/england/league-one",
    "ENG_L2": "football/england/league-two",
    "ENG_NL": "football/england/national-league",
    "SCO_PL": "football/scotland/premiership",
    "SCO_CH": "football/scotland/championship",
    "SCO_L1": "football/scotland/league-one",
    "SCO_L2": "football/scotland/league-two",
    "GER_BL": "football/germany/bundesliga",
    "GER_B2": "football/germany/2-bundesliga",
    "ITA_SA": "football/italy/serie-a",
    "ITA_SB": "football/italy/serie-b",
    "ESP_PD": "football/spain/laliga",
    "ESP_SD": "football/spain/laliga2",
    "FRA_L1": "football/france/ligue-1",
    "FRA_L2": "football/france/ligue-2",
    "NED_ED": "football/netherlands/eredivisie",
    "BEL_PL": "football/belgium/jupiler-pro-league",
    "POR_PL": "football/portugal/primeira-liga",
    "TUR_SL": "football/turkey/super-lig",
    "GRE_SL": "football/greece/super-league",
    "BRA_SA": "football/brazil/serie-a-betano",
    "MEX_LM": "football/mexico/liga-mx",
    "AUT_BL": "football/austria/bundesliga",
    "SWI_SL": "football/switzerland/super-league",
}


# Mapeamento de como a casa de apostas aparece no DOM (title/alt do img) 
# para o nosso canonical name (precisa bater exatamente com a tabela bookmakers)
FLASHSCORE_BOOKMAKER_MAP: Dict[str, str] = {
    # Casas internacionais / alvo principal (visíveis no Brasil)
    "bet365": "bet365",
    "Pinnacle": "pinnacle",
    "Betfair": "betfair_ex",
    "1xBet": "1xbet",
    "Betano": "betano",
    "Superbet": "superbet",
    "Unibet": "unibet",
    "Betway": "betway",
    "bwin": "bwin",
    "William Hill": "williamhill",
    "Marathonbet": "marathonbet",
    "Dafabet": "dafabet",
    "888sport": "888sport",
    # Variantes regionais (manter para fallback)
    "Betclic.fr": "betclic",
    "Unibet.fr": "unibet",
    "Betclic": "betclic",
}


@dataclass
class FlashscoreConfig:
    # Camoufox/Browser setup
    headless: bool = False  # Flashscore bloqueia odds em headless; rodar com xvfb-run na VPS
    page_timeout_ms: int = 40000
    render_wait_ms: int = 1500
    
    # Scraping limits
    discovery_max_scrolls: int = 3
    
    # Proxy NordVPN SOCKS5 (lê do .env para simular localização brasileira)
    proxy_server: Optional[str] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    
    def __post_init__(self):
        # Carrega proxy do .env se não foi passado explicitamente
        if not self.proxy_server:
            self.proxy_server = os.getenv("NORDVPN_PROXY_SERVER")
        if not self.proxy_username:
            self.proxy_username = os.getenv("NORDVPN_PROXY_USER")
        if not self.proxy_password:
            self.proxy_password = os.getenv("NORDVPN_PROXY_PASS")
    
    @property
    def proxy(self) -> Optional[dict]:
        """Retorna dict de proxy para Camoufox/Playwright, ou None se não configurado."""
        if self.proxy_server and self.proxy_username and self.proxy_password:
            return {
                "server": self.proxy_server,
                "username": self.proxy_username,
                "password": self.proxy_password,
            }
        return None
    
    # Estrutura de endpoints (hashes) para acessar as abas de odds na match page
    markets: Dict[str, dict] = field(default_factory=lambda: {
        "1x2_ft": {"sys_market": "1x2",  "period": "ft", "hash": "#/odds-comparison/1x2-odds/full-time"},
        "1x2_ht": {"sys_market": "1x2",  "period": "ht", "hash": "#/odds-comparison/1x2-odds/1st-half"},
        "ou_ft":  {"sys_market": "ou",   "period": "ft", "hash": "#/odds-comparison/over-under/full-time"},
        "ou_ht":  {"sys_market": "ou",   "period": "ht", "hash": "#/odds-comparison/over-under/1st-half"},
        "ah_ft":  {"sys_market": "ah",   "period": "ft", "hash": "#/odds-comparison/asian-handicap/full-time"},
        "ah_ht":  {"sys_market": "ah",   "period": "ht", "hash": "#/odds-comparison/asian-handicap/1st-half"},
        "btts":   {"sys_market": "btts", "period": "ft", "hash": "#/odds-comparison/both-teams-to-score/full-time"},
        "dc":     {"sys_market": "dc",   "period": "ft", "hash": "#/odds-comparison/double-chance/full-time"},
        "dnb":    {"sys_market": "dnb",  "period": "ft", "hash": "#/odds-comparison/draw-no-bet/full-time"},
    })
