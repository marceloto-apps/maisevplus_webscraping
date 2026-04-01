"""
T07 — Shot Collector
Pacotes JSONB e Agregadores de Métricas do Understat.
"""

def parse_shots_to_raw(shots_data: dict) -> dict:
    """
    Entrada: {'h': [shot1, shot2, ...], 'a': [shot1, ...]}
    Gera o payload estruturado raw_json.
    """
    if not shots_data:
        return {}

    home_shots_raw = shots_data.get('h', [])
    away_shots_raw = shots_data.get('a', [])
    
    # 1. Empacotar shots limpos
    def _clean_shot(s: dict):
        return {
            'minute': int(s.get('minute', 0)),
            'x': float(s.get('X', 0)),
            'y': float(s.get('Y', 0)),
            'xG': float(s.get('xG', 0)),
            'result': s.get('result', ''),
            'situation': s.get('situation', ''),
            'player': s.get('player', ''),
            'player_id': int(s.get('player_id', 0)) if s.get('player_id') else None
        }

    home_shots = [_clean_shot(s) for s in home_shots_raw]
    away_shots = [_clean_shot(s) for s in away_shots_raw]

    # 2. Cálculos agregados precisos
    xg_h = sum(s['xG'] for s in home_shots)
    xg_a = sum(s['xG'] for s in away_shots)
    
    s_h = len(home_shots)
    s_a = len(away_shots)
    
    is_sot = lambda s: s['result'] in ('Goal', 'SavedShot')
    sot_h = sum(1 for s in home_shots if is_sot(s))
    sot_a = sum(1 for s in away_shots if is_sot(s))
    
    # Deep completions (pseudo-estimativa por coordenada x > 0.88 dentro da area)
    # A métrica real de PPDA etc vem das subrotinas globais do Understat, mas
    # deixamos zero pra não quebrar padroes.
    is_deep = lambda s: s['x'] > 0.88
    deep_h = sum(1 for s in home_shots if is_deep(s))
    deep_a = sum(1 for s in away_shots if is_deep(s))

    return {
        'source': 'understat',
        'model_version': '1.0',
        'home_shots': home_shots,
        'away_shots': away_shots,
        'aggregated': {
            'xg_home': round(xg_h, 3),
            'xg_away': round(xg_a, 3),
            'shots_home': s_h,
            'shots_away': s_a,
            'sot_home': sot_h,
            'sot_away': sot_a,
            'deep_home': deep_h,
            'deep_away': deep_a,
            'ppda_home': None, 
            'ppda_away': None
        }
    }


UNDERSTAT_FIELD_MAP = {
    # Nossas colunas reais tipadas
    'xg_home': ('match_stats', 'xg_home', 'float'),
    'xg_away': ('match_stats', 'xg_away', 'float'),
    # Extrai isso direto do payload master
    'raw_json': ('match_stats', 'raw_json', 'jsonb'),
}


class ShotCollector:
    @staticmethod
    def extract_metrics(shots_data: dict) -> dict:
        """
        Gera o dicionario pronto pra virar KWARGS do DB
        """
        raw_json_dict = parse_shots_to_raw(shots_data)
        
        agg = raw_json_dict.get('aggregated', {})
        
        return {
            'raw_json': raw_json_dict,
            'xg_home': agg.get('xg_home'),
            'xg_away': agg.get('xg_away')
        }
