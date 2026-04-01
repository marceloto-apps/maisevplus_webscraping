"""
T06 — src/tests/test_footystats.py
Testes unitários rigorosos focados na limpeza de tipos da Footystats (Nulos e JSONB array)
"""
import pytest
import json
from datetime import datetime

from src.collectors.footystats.matches_collector import MatchesCollector

@pytest.fixture
def sample_raw_match():
    return {
        "id": 1699923,
        "homeID": 105,
        "awayID": 110,
        "status": "complete",
        "date_unix": 1600000000,
        "homeGoalCount": 2,
        "awayGoalCount": 0,
        "ht_goals_team_a": 1,
        "ht_goals_team_b": 0,
        "team_a_goal_timings": "45,89",
        "team_b_goal_timings": "-1",
        "team_a_xg": 2.15,
        "team_b_xg": -1.0,
        "team_a_possession": 45,
        "team_b_possession": 55,
        "team_a_corners": 10,
        "team_b_corners": -1,
        "team_a_yellow_cards": 2,
        "team_b_yellow_cards": 0,
        "goalTimingDistributed": "0-15:0, 16-30:0, 31-45+:1, 46-60:0, 61-75:0, 76-90+:1"
    }

def test_clean_stat():
    """Valida que -1 converte para nulo mas 0.0, 1 e outros não."""
    from src.collectors.footystats.matches_collector import clean_stat
    assert clean_stat(-1) is None
    assert clean_stat("-1") is None
    assert clean_stat(0) == 0
    assert clean_stat("0") == 0
    assert clean_stat(10) == 10

def test_clean_xg():
    """Valida xG negativo ou bugados."""
    from src.collectors.footystats.matches_collector import clean_xg
    assert clean_xg(-1.5) is None
    assert clean_xg(0.0) == 0.0
    assert clean_xg(1.0) == 1.0
    assert clean_xg("2.45") == 2.45

def test_clean_possession():
    """Valida zeração de posse num jogo completo bugado pela API."""
    from src.collectors.footystats.matches_collector import clean_possession
    assert clean_possession(-1) is None
    assert clean_possession(0, 'complete') is None
    assert clean_possession(0, 'finished') is None
    assert clean_possession(0, 'scheduled') == 0.0 # Se for futuro ou incomum, 0 é aceitavel? O field is none on upcoming actually.
    assert clean_possession(45) == 45.0

def test_matches_collector_parse(sample_raw_match):
    """Garante que a arvore JSONB final gera as rows das 2 tabelas perfeitas"""
    parsed = MatchesCollector.parse_raw_match(sample_raw_match)
    
    m = parsed['matches']
    s = parsed['match_stats']
    
    # Conferindo `matches` (Shallow table)
    assert m['ft_home'] == 2
    assert m['ht_away'] == 0
    assert json.loads(m['home_goal_minutes']) == [45, 89]
    assert m['away_goal_minutes'] is None  # Era "-1" no payload
    assert isinstance(m['kickoff'], datetime)
    
    # Conferindo `match_stats` (Deep table)
    assert s['home_xg'] == 2.15
    assert s['away_xg'] is None  # Era -1 no payload
    assert s['home_corners'] == 10
    assert s['away_corners'] is None # Era -1
    
    dist = json.loads(s['goal_timing_distribution'])
    assert dist["0-15"] == 0
    assert dist["31-45+"] == 1
    assert dist["76-90+"] == 1
