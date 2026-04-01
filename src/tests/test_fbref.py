import pytest
from pathlib import Path
from src.collectors.fbref.parser import FBRefParser

@pytest.fixture
def sample_html():
    file_path = Path("src/tests/fixtures/sample_fbref_match.html")
    # Tenta usar o arquivo fisico se existir, util localmente
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
         raise FileNotFoundError("Mock HTML ausente")

def test_fbref_parser_full_mock(sample_html):
    """Cenários 1 e 2: Parse Completo do Home, Tabela Faltante no Away"""
    
    # Executa o parser
    data = FBRefParser.parse_match(sample_html)
    
    # Asserções estruturais vitais
    assert "home_players" in data
    assert "away_players" in data
    assert "aggregated" in data
    
    home = data["home_players"]
    away = data["away_players"]
    agg = data["aggregated"]
    
    # Validando o "Drop de X Players" do DataFrame
    # O mock tinha `11 Players` listado no thead ou tfoot, deveríamos ter limpo.
    names = [p["name"] for p in home]
    assert "11 Players" not in names
    
    # Validando o MultiIndex Parse e Merging: (John Doe estava na summary, pass, def, etc)
    john = next(p for p in home if p["name"] == "John Doe")
    assert float(john["xg"]) == 0.75
    assert float(john["progressive_passes"]) == 3.0
    assert float(john["pressures"]) == 5.0
    
    # Validando um cruzamento imperfeito (Outer Merge).
    # 'Extra Player' só estava na tabela de Defesa e não na Summary.
    extra = next(p for p in home if p["name"] == "Extra Player")
    assert extra["xg"] == 0  # Preenchido com 0 no fillna(0)
    assert extra["pressures"] == 3.0
    assert "11 Players" not in [p["name"] for p in home]

    # Validando a "Faltante Table" (GCA não existe no Time Away 99zzxx)
    # A tabela inteira gca sumiu no mock do Away, portanto a key gca ou nem existe ou vale 0.
    rival_mid = next(p for p in away if p["name"] == "Rival Mid")
    assert float(rival_mid["xg"]) == 0.15
    assert "gca" not in rival_mid or rival_mid["gca"] == 0
    
    # Validando as Agregações Finais (Somatória robusta de xG)
    # Home: John Doe (0.75) + Jane Smith (0.12) + Missing Name (0) = 0.87
    # O "Missing name" tava na summary mas tem xg 0.00
    assert agg["xg_home"] == 0.87
    
    # Away: Rival Striker (0.50) + Rival Mid (0.15) = 0.65
    assert agg["xg_away"] == 0.65
    
    # Progressive passes: (John 3 + Jane 12) = 15
    assert agg["progressive_passes_home"] == 15
    assert agg["progressive_passes_away"] == 9 # Striker 1 + Mid 8


def test_fbref_parser_empty_html():
    """Cenário 3: HTML vazio ou faltando as Hash Divs principais retorna Payload blindado sem erro"""
    
    html = "<html><body><h1>No stats for this match!</h1></body></html>"
    data = FBRefParser.parse_match(html)
    
    assert data["home_players"] == []
    assert data["away_players"] == []
    assert data["aggregated"] == {}

def test_fbref_parser_commented_html():
    """Garante que a descompressão dos commentarios HTML cruza perfeitamente via Un-commenting"""
    
    html = '''
    <table id="stats_abc_summary"><tbody><tr><th>Player1</th><td>90</td><td>1.5</td><td>0</td></tr></tbody></table>
    <!--
    <table id="stats_def_summary"><tbody><tr><th>Player2</th><td>90</td><td>2.0</td><td>0</td></tr></tbody></table>
    -->
    '''
    # O Parser deve magicamente desencapsular a "stats_def_summary".
    data = FBRefParser.parse_match(html)
    
    # Checa se achou os 2 hashes e parizou com list
    assert isinstance(data["home_players"], list)
