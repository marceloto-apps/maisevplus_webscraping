from dataclasses import dataclass, field
from typing import Dict

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
    "ARG_LP": "football/argentina/liga-profesional",
    "CHI_LDP": "football/chile/liga-de-primera",
    "USA_MLS": "football/usa/mls",
    "BRA_SB": "football/brazil/serie-b",
    "NOR_ELI": "football/norway/eliteserien",
    "JPN_J1": "football/japan/j1-league",
    "SWE_ALL": "football/sweden/allsvenskan",
    "FIN_VEI": "football/finland/veikkausliiga",
    "CHN_SL": "football/china/super-league",
    "PER_L1": "football/peru/liga-1",
    "URU_LAU": "football/uruguay/liga-auf-uruguaia",
    "COL_PA": "football/colombia/primera-a",
    "PAR_CP": "football/paraguay/copa-de-primera",
    "ECU_LP": "football/ecuador/liga-pro",
    "BOL_DP": "football/bolivia/divisao-profissional",
    "USA_USC": "football/usa/usl-championship",
    "USA_USL1": "football/usa/usl-league-one",
    "CAN_PL": "football/canada/canadian-premier-league",
    "SWE_SUP": "football/sweden/superettan",
    "NOR_OBOS": "football/norway/obos-ligaen",
    "FIN_YKK": "football/finland/ykkosliiga",
    "JPN_J2": "football/japan/j2-league",
    "KOR_K1": "football/south-korea/k-league-1",
    "KOR_K2": "football/south-korea/k-league-2",
    "IRL_PD": "football/ireland/premier-division",
}


# Mapeamento de como a casa de apostas aparece no DOM (title/alt do img) 
# para o nosso canonical name (precisa bater exatamente com a tabela bookmakers)
# A VPS deve rodar com NordVPN conectada ao Brasil para receber bookmakers BR.
_RAW_BOOKMAKER_MAP: Dict[str, str] = {
    # Casas principais
    "bet365": "bet365",
    "Betfair": "betfair_ex",
    "Betano.br": "betano",
    "1xBet.br": "1xbet",
    "Superbet.br": "superbet",
    "Pinnacle": "pinnacle",
    # Casas secundárias ativas
    "Betnacional": "betnacional",
    "KTO.br": "kto",
    "Estrelabet": "estrela_bet",
    "F12": "f12",
    "Multibet.br": "multibet",
    "Bet7k": "bet7k",
    "SeguroBet": "segurobet",
    # EXCLUÍDAS (não mapear): esportesdasorte, betesporte, br4bet, casadeapostas,
    # luvabet, betdasorte, betboom, esportivabet, brasilbet, brasildasorte,
    # goldebet, jogodeouro, lotogreen, alfabet
}

FLASHSCORE_BOOKMAKER_MAP = {k.strip().lower(): v for k, v in _RAW_BOOKMAKER_MAP.items()}

def resolve_bookmaker(raw_name: str) -> str | None:
    """
    Resolve o nome raw extraído do DOM para o nome canônico.
    Retorna None se não encontrar (bookmaker desconhecido).
    """
    if not raw_name:
        return None
    return FLASHSCORE_BOOKMAKER_MAP.get(raw_name.strip().lower())


@dataclass
class FlashscoreConfig:
    # Camoufox/Browser setup
    # Flashscore bloqueia odds em headless; rodar com xvfb-run na VPS
    headless: bool = False
    page_timeout_ms: int = 40000
    render_wait_ms: int = 1500
    
    # Scraping limits
    discovery_max_scrolls: int = 3
    
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
