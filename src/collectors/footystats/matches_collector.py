"""
T06 — Footystats Matches Collector
Recebe raw objects consolidados via JSON API e varre a estrutura transformando
strings ruidosas e tipos falhos nos datatypes exatos definidos pelo BD.
"""
from datetime import datetime, timezone
import json
from typing import Dict, Any, Optional, List

from ...db.logger import get_logger

logger = get_logger(__name__)

# =========================================================================
# FUNÇÕES DE LIMPEZA (CLEANERS)
# =========================================================================

def clean_stat(value: Any) -> Optional[int]:
    """Limpa contadores brutos onde a Footystats devolve -1 como anomalia."""
    if value is None:
        return None
    try:
        val = int(value)
        return None if val == -1 else val
    except (ValueError, TypeError):
        return None

def clean_xg(value: Any) -> Optional[float]:
    """Valores de xG falhos costumam vir negativos ou ausentes."""
    if value is None:
        return None
    try:
        val = float(value)
        return None if val < 0 else val
    except (ValueError, TypeError):
        return None

def clean_possession(value: Any, match_status: str = 'complete') -> Optional[float]:
    """Tratamento atencioso para zeros de posse que mascaram desastres da provider."""
    if value is None:
        return None
    try:
        val = float(value)
        if val == -1:
            return None
        if val == 0 and match_status in ('complete', 'finished'):
            return None  # Jogos completos não podem ter 0% de bola dividida
        return val
    except (ValueError, TypeError):
        return None

def parse_csv_minutes(val: Any) -> Optional[List[int]]:
    """'23,67,89' -> [23, 67, 89]"""
    if not val or val == '-1':
        return None
    if isinstance(val, list):
        return [int(m) for m in val if str(m).strip().isdigit()]
    if isinstance(val, str):
        return [int(m.strip()) for m in val.split(',') if m.strip().isdigit()]
    return None

def parse_distribution(val: Any) -> Optional[dict]:
    """'0-10:0, 11-20:1, ...' -> {'0-10': 0, '11-20': 1}"""
    if not val or val == '-1':
        return None
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        pairs = [p.strip().split(':') for p in val.split(',') if ':' in p]
        return {str(k): int(v) for k, v in pairs if str(v).strip().isdigit()}
    return None

def parse_kickoff(v: Any) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc)
    except (ValueError, TypeError):
        return None


# =========================================================================
# MAPA CENTRAL DE CAMPOS
# Define a anatomia inteira do scraping para as Queries assíncronas do BD
# =========================================================================

FOOTYSTATS_FIELD_MAP = {
    # Tabela MATCHES (Estatísticas Rasas / Meta)
    'date_unix':           ('matches', 'kickoff', 'timestamp', parse_kickoff),
    'homeGoalCount':       ('matches', 'ft_home', 'int', lambda v: int(v) if v is not None and v != "" else None),
    'awayGoalCount':       ('matches', 'ft_away', 'int', lambda v: int(v) if v is not None and v != "" else None),
    'ht_goals_team_a':     ('matches', 'ht_home', 'int', clean_stat),
    'ht_goals_team_b':     ('matches', 'ht_away', 'int', clean_stat),
    'team_a_goal_timings': ('matches', 'home_goal_minutes', 'jsonb', parse_csv_minutes),
    'team_b_goal_timings': ('matches', 'away_goal_minutes', 'jsonb', parse_csv_minutes),

    # Tabela MATCH_STATS (Deep Stats p/ ML)
    'team_a_xg':           ('match_stats', 'home_xg', 'float', clean_xg),
    'team_b_xg':           ('match_stats', 'away_xg', 'float', clean_xg),
    'team_a_corners':      ('match_stats', 'home_corners', 'int', clean_stat),
    'team_b_corners':      ('match_stats', 'away_corners', 'int', clean_stat),
    'team_a_yellow_cards': ('match_stats', 'home_yellow', 'int', clean_stat),
    'team_b_yellow_cards': ('match_stats', 'away_yellow', 'int', clean_stat),
    'team_a_red_cards':    ('match_stats', 'home_red', 'int', clean_stat),
    'team_b_red_cards':    ('match_stats', 'away_red', 'int', clean_stat),
    'team_a_possession':   ('match_stats', 'home_possession', 'float', clean_possession), # Closure bound
    'team_b_possession':   ('match_stats', 'away_possession', 'float', clean_possession), # Closure bound
    'team_a_shots':        ('match_stats', 'home_shots', 'int', clean_stat),
    'team_b_shots':        ('match_stats', 'away_shots', 'int', clean_stat),
    'team_a_shotsOnTarget':('match_stats', 'home_shots_on_target', 'int', clean_stat),
    'team_b_shotsOnTarget':('match_stats', 'away_shots_on_target', 'int', clean_stat),
    'goalTimingDistributed':('match_stats', 'goal_timing_distribution', 'jsonb', parse_distribution),
}

class MatchesCollector:
    """
    Parser Puro de Matches do FootyStats
    """
    @staticmethod
    def parse_raw_match(raw_match: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Engole o match bruto e separa em duas entidades prontas
        pra entrar como kwargs de INSERT no DB (matches vs match_stats).
        """
        status = raw_match.get('status', 'complete').lower()
        
        parsed = {
            'matches': {},
            'match_stats': {}
        }
        
        for fs_key, (table, col, dtype, cleaner) in FOOTYSTATS_FIELD_MAP.items():
            raw_val = raw_match.get(fs_key)
            
            if cleaner:
                if cleaner == clean_possession:
                    val = cleaner(raw_val, match_status=status)
                else:
                    val = cleaner(raw_val)
            else:
                val = raw_val

            if dtype == 'jsonb' and val is not None:
                val = json.dumps(val)

            parsed[table][col] = val
        
        return parsed
