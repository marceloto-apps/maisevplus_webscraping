"""
T07 — src/tests/test_understat.py
Testes unitários rigorosos focados na resiliência do Web Scraping HTML via Regex
"""
import pytest
from src.collectors.understat.scraper import UnderstatScraper
from src.collectors.understat.shot_collector import parse_shots_to_raw

FAKE_HTML = r"""
<!DOCTYPE html>
<html>
<body>
    <script>
        // Caso primario: JSON.parse
        var shotsData = JSON.parse('\x7B\x22h\x22\x3A\x5B\x7B\x22minute\x22\x3A\x2223\x22,\x22result\x22\x3A\x22Goal\x22,\x22xG\x22\x3A\x220.12\x22\x7D\x5D,\x22a\x22\x3A\x5B\x5D\x7D');
    </script>
    <script>
        // Caso alternativo fallback direto
        var datesData = [{"id":"123","datetime":"2023-08-11 20:00:00","h":{"title":"Burnley"},"a":{"title":"Man City"}}];
    </script>
</body>
</html>
"""

def test_extract_var_json_parse():
    """Valida que o wrapper do regex quebra o unicode_esacpe perfeitamente"""
    scraper = UnderstatScraper()
    
    # Extrai o shotsData do FAKE_HTML
    data = scraper._extract_var(FAKE_HTML, 'shotsData')
    
    assert data is not None
    assert 'h' in data
    assert len(data['h']) == 1
    assert data['h'][0]['result'] == 'Goal'
    assert data['h'][0]['xG'] == "0.12"
    
def test_extract_var_assignment_fallback():
    """Valida o fallback de varre variavel sem JSON.parse() -> var datesData = [{...}]"""
    scraper = UnderstatScraper()
    
    data = scraper._extract_var(FAKE_HTML, 'datesData')
    
    assert data is not None
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]['id'] == '123'
    assert data[0]['h']['title'] == 'Burnley'

def test_pack_raw_json():
    """Valida o empacotamento do raw_json e os counters agragados"""
    shots_data = {
        'h': [
            {'minute': "23", 'result': 'Goal', 'xG': '0.12', 'X': '0.89', 'Y': '0.5'},
            {'minute': "45", 'result': 'SavedShot', 'xG': '0.05', 'X': '0.1', 'Y': '0.5'}
        ],
        'a': [
            {'minute': "88", 'result': 'MissedShots', 'xG': '0.10', 'X': '0.3', 'Y': '0.5'}
        ]
    }
    
    raw = parse_shots_to_raw(shots_data)
    
    assert raw['source'] == 'understat'
    assert len(raw['home_shots']) == 2
    assert len(raw['away_shots']) == 1
    
    agg = raw['aggregated']
    # xG home = 0.12 + 0.05 = 0.17
    assert agg['xg_home'] == 0.17
    assert agg['xg_away'] == 0.10
    
    # Shots
    assert agg['shots_home'] == 2
    assert agg['shots_away'] == 1
    
    # SoT
    assert agg['sot_home'] == 2 # Goal e SavedShot
    assert agg['sot_away'] == 0
    
    # Deep
    assert agg['deep_home'] == 1 # Apenas o primeiro tem X > 0.88
    assert agg['deep_away'] == 0
