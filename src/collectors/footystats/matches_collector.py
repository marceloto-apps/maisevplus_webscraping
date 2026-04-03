"""
T06 — Footystats Matches Collector
Recebe raw objects consolidados via JSON API e varre a estrutura transformando
strings ruidosas e tipos falhos nos datatypes exatos definidos pelo BD.
"""
from datetime import datetime, timezone
import json
from typing import Dict, Any, List

from ...db.logger import get_logger

logger = get_logger(__name__)

# =========================================================================
# FUNÇÕES DE LIMPEZA (CLEANERS)
# Política ZERO-NULL: inteiros → 0, floats → 0.0, jsonb → []
# =========================================================================

def clean_stat(value: Any) -> int:
    """Limpa contadores brutos. Retorna 0 para qualquer anomalia (-1, vazio, None)."""
    if value is None or value == '' or value == '-1':
        return 0
    try:
        val = int(value)
        return 0 if val < 0 else val
    except (ValueError, TypeError):
        return 0

def clean_xg(value: Any) -> float:
    """Valores de xG. Retorna 0.0 para qualquer anomalia."""
    if value is None or value == '' or value == '-1':
        return 0.0
    try:
        val = float(value)
        return 0.0 if val < 0 else round(val, 2)
    except (ValueError, TypeError):
        return 0.0

def clean_possession(value: Any, match_status: str = 'complete') -> float:
    """Tratamento para posse de bola. Retorna 0.0 para anomalias."""
    if value is None or value == '' or value == '-1':
        return 0.0
    try:
        val = float(value)
        return 0.0 if val < 0 else round(val, 1)
    except (ValueError, TypeError):
        return 0.0

def parse_csv_minutes(val: Any) -> list:
    """
    Converte timings de gols para lista de inteiros.
    API retorna como lista Python: [4, 38, 71]
    Também aceita CSV string: '23,67,89'
    Retorna [] para vazio/ausente (NUNCA None).
    """
    if val is None or val == -1 or val == '-1':
        return []
    if isinstance(val, list):
        # API retorna ['8', '31', '90+3'] como strings!
        # Também pode vir como ints em alguns casos.
        # '90+3' → pegar só a parte antes do '+' = 90
        result = []
        for m in val:
            try:
                s = str(m).strip()
                # Tratar acréscimos: '90+3' → 90
                if '+' in s:
                    s = s.split('+')[0]
                result.append(int(s))
            except (ValueError, TypeError):
                continue
        return result
    if isinstance(val, str):
        val = val.strip()
        if not val or val == '-1':
            return []
        return [int(m.strip()) for m in val.split(',') if m.strip().isdigit()]
    return []

def parse_distribution(val: Any) -> dict:
    """'0-10:0, 11-20:1, ...' -> {'0-10': 0, '11-20': 1}"""
    if not val or val == '-1':
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        pairs = [p.strip().split(':') for p in val.split(',') if ':' in p]
        return {str(k): int(v) for k, v in pairs if str(v).strip().isdigit()}
    return {}

def parse_kickoff(v: Any):
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc)
    except (ValueError, TypeError):
        return None


# =========================================================================
# MAPA CENTRAL DE CAMPOS
# Define a anatomia inteira do scraping para as Queries assíncronas do BD
# Ordem segue a coluna na tabela match_stats (migration 011)
# =========================================================================

FOOTYSTATS_FIELD_MAP = {
    # Tabela MATCHES (Estatísticas Rasas / Meta)
    'date_unix':           ('matches', 'kickoff', 'timestamp', parse_kickoff),
    'homeGoalCount':       ('matches', 'ft_home', 'int', lambda v: int(v) if v is not None and v != "" else None),
    'awayGoalCount':       ('matches', 'ft_away', 'int', lambda v: int(v) if v is not None and v != "" else None),
    'ht_goals_team_a':     ('matches', 'ht_home', 'int', clean_stat),
    'ht_goals_team_b':     ('matches', 'ht_away', 'int', clean_stat),

    # Tabela MATCH_STATS (Deep Stats p/ ML) — ordem da tabela
    'team_a_xg':           ('match_stats', 'xg_home', 'float', clean_xg),
    'team_b_xg':           ('match_stats', 'xg_away', 'float', clean_xg),
    'totalGoalCount':      ('match_stats', 'total_goals_ft', 'int', clean_stat),
    'homeGoals_timings':   ('match_stats', 'goals_home_minutes', 'jsonb', parse_csv_minutes),
    'awayGoals_timings':   ('match_stats', 'goals_away_minutes', 'jsonb', parse_csv_minutes),

    'team_a_corners':      ('match_stats', 'corners_home_ft', 'int', clean_stat),
    'team_b_corners':      ('match_stats', 'corners_away_ft', 'int', clean_stat),

    'team_a_offsides':     ('match_stats', 'offsides_home', 'int', clean_stat),
    'team_b_offsides':     ('match_stats', 'offsides_away', 'int', clean_stat),
    'team_a_yellow_cards': ('match_stats', 'yellow_cards_home_ft', 'int', clean_stat),
    'team_b_yellow_cards': ('match_stats', 'yellow_cards_away_ft', 'int', clean_stat),
    'team_a_red_cards':    ('match_stats', 'red_cards_home_ft', 'int', clean_stat),
    'team_b_red_cards':    ('match_stats', 'red_cards_away_ft', 'int', clean_stat),

    'team_a_shotsOnTarget':('match_stats', 'shots_on_target_home', 'int', clean_stat),
    'team_b_shotsOnTarget':('match_stats', 'shots_on_target_away', 'int', clean_stat),
    'team_a_shotsOffTarget':('match_stats', 'shots_off_target_home', 'int', clean_stat),
    'team_b_shotsOffTarget':('match_stats', 'shots_off_target_away', 'int', clean_stat),
    'team_a_shots':        ('match_stats', 'shots_home', 'int', clean_stat),
    'team_b_shots':        ('match_stats', 'shots_away', 'int', clean_stat),

    'team_a_fouls':        ('match_stats', 'fouls_home', 'int', clean_stat),
    'team_b_fouls':        ('match_stats', 'fouls_away', 'int', clean_stat),
    'team_a_possession':   ('match_stats', 'possession_home', 'float', clean_possession),
    'team_b_possession':   ('match_stats', 'possession_away', 'float', clean_possession),
    'btts_potential':      ('match_stats', 'btts_potential', 'float', clean_xg),

    'team_a_fh_corners':   ('match_stats', 'corners_home_ht', 'int', clean_stat),
    'team_b_fh_corners':   ('match_stats', 'corners_away_ht', 'int', clean_stat),
    'team_a_2h_corners':   ('match_stats', 'corners_home_2h', 'int', clean_stat),
    'team_b_2h_corners':   ('match_stats', 'corners_away_2h', 'int', clean_stat),

    'goals_2hg_team_a':    ('match_stats', 'goals_home_2h', 'int', clean_stat),
    'goals_2hg_team_b':    ('match_stats', 'goals_away_2h', 'int', clean_stat),

    'team_a_fh_cards':     ('match_stats', 'cards_home_ht', 'int', clean_stat),
    'team_b_fh_cards':     ('match_stats', 'cards_away_ht', 'int', clean_stat),
    'team_a_2h_cards':     ('match_stats', 'cards_home_2h', 'int', clean_stat),
    'team_b_2h_cards':     ('match_stats', 'cards_away_2h', 'int', clean_stat),

    'team_a_dangerous_attacks':('match_stats', 'dangerous_attacks_home', 'int', clean_stat),
    'team_b_dangerous_attacks':('match_stats', 'dangerous_attacks_away', 'int', clean_stat),
    'team_a_attacks':      ('match_stats', 'attacks_home', 'int', clean_stat),
    'team_b_attacks':      ('match_stats', 'attacks_away', 'int', clean_stat),

    'team_a_0_10_min_goals':  ('match_stats', 'goals_home_0_10_min', 'int', clean_stat),
    'team_b_0_10_min_goals':  ('match_stats', 'goals_away_0_10_min', 'int', clean_stat),
    'team_a_corners_0_10_min':('match_stats', 'corners_home_0_10_min', 'int', clean_stat),
    'team_b_corners_0_10_min':('match_stats', 'corners_away_0_10_min', 'int', clean_stat),
    'team_a_cards_0_10_min':  ('match_stats', 'cards_home_0_10_min', 'int', clean_stat),
    'team_b_cards_0_10_min':  ('match_stats', 'cards_away_0_10_min', 'int', clean_stat),

    'home_ppg':                    ('match_stats', 'home_ppg', 'float', clean_xg),
    'away_ppg':                    ('match_stats', 'away_ppg', 'float', clean_xg),
    'pre_match_home_ppg':          ('match_stats', 'pre_match_home_ppg', 'float', clean_xg),
    'pre_match_away_ppg':          ('match_stats', 'pre_match_away_ppg', 'float', clean_xg),
    'pre_match_teamA_overall_ppg': ('match_stats', 'pre_match_overall_ppg_home', 'float', clean_xg),
    'pre_match_teamB_overall_ppg': ('match_stats', 'pre_match_overall_ppg_away', 'float', clean_xg),
    'team_a_xg_prematch':          ('match_stats', 'xg_prematch_home', 'float', clean_xg),
    'team_b_xg_prematch':          ('match_stats', 'xg_prematch_away', 'float', clean_xg),
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

            if dtype == 'jsonb':
                # asyncpg exige string JSON para JSONB — serializar sempre
                if val is None:
                    val = json.dumps([])
                else:
                    val = json.dumps(val)

            parsed[table][col] = val
        
        return parsed
