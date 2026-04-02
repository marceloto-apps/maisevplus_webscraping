"""
Construtor de URLs do BetExplorer a partir de league codes e parâmetros.
"""
from .config import BASE_URL, LEAGUE_BETEXPLORER_PATHS

def build_results_url(slug: str, season: str = "") -> str:
    """URL da página de resultados de uma liga."""
    if season:
        return f"{BASE_URL}/football/{slug}-{season}/results/"
    return f"{BASE_URL}/football/{slug}/results/"

def build_fixtures_url(slug: str, season: str = "") -> str:
    """URL da página de fixtures de uma liga."""
    if season:
        return f"{BASE_URL}/football/{slug}-{season}/fixtures/"
    return f"{BASE_URL}/football/{slug}/fixtures/"

def build_match_url(slug: str, match_slug: str, match_id: str) -> str:
    """URL de um jogo específico."""
    return f"{BASE_URL}/football/{slug}/{match_slug}/{match_id}/"

def build_league_url(league_code: str, mode: str = "results", season: str = "") -> str:
    """Converte league_code → URL completa."""
    slug = LEAGUE_BETEXPLORER_PATHS.get(league_code)
    if not slug:
        raise ValueError(f"Liga {league_code} não mapeada")
    if mode == "fixtures":
        return build_fixtures_url(slug, season)
    return build_results_url(slug, season)
