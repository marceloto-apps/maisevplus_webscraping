import os
from typing import Dict, Any
from datetime import date
import yaml
from src.db.helpers import fetch_all
from src.db.logger import get_logger

logger = get_logger(__name__)

LEAGUE_DEFAULTS = {
    "api_football_league_id": None,
    "odds_api_sport_key": None,
    "understat_name": None,
    "fbref_id": None,
    "football_data_code": None,
    "football_data_type": None,
}

class ConfigLoader:
    _leagues_cache = None

    @classmethod
    def get_cached_leagues(cls) -> Dict[str, Any]:
        """Retorna cache já carregado. Raises se init não rodou."""
        if cls._leagues_cache is None:
            raise RuntimeError("ConfigLoader.load_leagues() não foi chamado durante init")
        return cls._leagues_cache

    @classmethod
    async def load_leagues(cls, reload_cache: bool = False) -> Dict[str, Any]:
        """
        Carrega leagues.yaml, injeta os defaults estruturais e consulta o DB
        para recuperar a map interna do `league_id` a partir do `code`.
        O resultado é guardado m cache em memória.
        """
        if cls._leagues_cache is not None and not reload_cache:
            return cls._leagues_cache

        base_dir = os.path.dirname(os.path.abspath(__file__))
        yaml_path = os.path.join(base_dir, "leagues.yaml")
        
        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)["leagues"]

        # Aplica Defaults preventivos (fail-safe)
        for league_code, league_data in raw.items():
            for field, default in LEAGUE_DEFAULTS.items():
                league_data.setdefault(field, default)

        # Hydrate ID via DDL `leagues` in a single query
        codes = list(raw.keys())
        query = "SELECT league_id, code FROM leagues WHERE code = ANY($1) AND is_active = TRUE;"
        # we need to simulate fetch_all, fetch already returns a list of records
        db_leagues = await fetch_all(query, codes)
        db_map = {row["code"]: row["league_id"] for row in db_leagues}

        # Injete o DB ID e filtre o estado da season!
        for league_code, league_data in raw.items():
            league_data["league_id"] = db_map.get(league_code)
            
            if not league_data["league_id"]:
                logger.warning("league_not_in_db", code=league_code)
            
            # Filtra Season Ativa baseado nas rules (aug_may, jul_may, annual)
            season_format = league_data.get("season_format", "aug_may")
            
            seasons = league_data.get("seasons", {})
            for season_key, season_obj in seasons.items():
                if not season_obj.get("footystats"):
                    logger.warning("missing_footystats_id", code=league_code, season=season_key)
                season_obj["active"] = cls.is_season_active(season_key, season_format, date.today())
                
        cls._leagues_cache = raw
        return raw

    @staticmethod
    def is_season_active(season_key: str, season_format: str, today: date) -> bool:
        """Infere ativação baseada na época do ano."""
        try:
            if season_format == "annual":
                # Apenas a temporada do ano corrente é ativa.
                # Para backfill de anos anteriores, usar flag manual ou CLI.
                return str(today.year) == season_key
            
            start_year = int(season_key.split("/")[0])
            
            if season_format == "aug_may":
                start = date(start_year, 8, 1)
                end = date(start_year + 1, 6, 30) # margem para playoffs
            elif season_format == "jul_may":
                start = date(start_year, 7, 1)
                end = date(start_year + 1, 6, 30) # margem para playoffs
            else:
                return False
                
            return start <= today <= end
        except Exception:
            return False
