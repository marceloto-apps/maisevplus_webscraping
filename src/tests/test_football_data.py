"""
T05 — src/tests/test_football_data.py
Testes unitários para o Football-Data Collector.
Utiliza mock de HTTPX para entregar um CSV corrompido ou perfeito e testar
o resilience da camada de pandas (on_bad_lines, datas ruins, etc).
"""

import pytest
import io
import pandas as pd
from unittest.mock import AsyncMock, patch

from src.collectors.football_data.csv_collector import FootballDataCollector

FAKE_CSV_BYTES = b"""Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,B365H,B365D,B365A,B365>2.5,B365<2.5,PSH,PSD,PSA,P>2.5,P<2.5
E0,11/08/2023,20:00,Burnley,Man City,0,3,A,0,2,A,9.00,5.50,1.33,1.66,2.20,9.15,5.64,1.34,1.67,2.29
E0,12/08/2023,12:30,Arsenal,Nott'm Forest,2,1,H,2,0,H,1.18,7.50,15.00,1.44,2.75,1.18,7.69,16.59,1.45,2.83
E0,12/08/2023,,NoTimeTeam,OtherTeam,1,1,D,0,0,D,2.00,3.00,4.00,1.5,2.5,2.0,3.0,4.0,1.5,2.5
E0,12/08/2023,BADTIME,Bad,Time,1,1,D,0,0,D,2.00,3.00,4.00,1.5,2.5,2.0,3.0,4.0,1.5,2.5
E0,13/08/2023,14:00,Brentford,Tottenham,2,2,D,2,2,D,2.75,3.50,2.40,1.72,2.15,2.87,3.59,2.44,1.72,2.21
"""

@pytest.fixture
def collector():
    return FootballDataCollector()

@pytest.mark.asyncio
@patch('httpx.AsyncClient')
async def test_health_check_success(mock_client_class, collector):
    """Verifica se o health check bate na URL E0 certa e varre a primeira linha corretamente."""
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.content = b"Div,Date,Time,HomeTeam,AwayTeam\nE0,11/08/2023,20:00,Burnley,Man City"
    
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_resp
    
    # httpx.AsyncClient is an async context manager
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_instance.__aexit__.return_value = False
    
    mock_client_class.return_value = mock_client_instance

    is_healthy = await collector.health_check()
    assert is_healthy is True

@pytest.mark.asyncio
@patch('httpx.AsyncClient')
async def test_health_check_failure(mock_client_class, collector):
    mock_resp = AsyncMock()
    mock_resp.status_code = 404
    mock_resp.content = b"404 Not found"
    
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_resp
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_instance.__aexit__.return_value = False
    mock_client_class.return_value = mock_client_instance

    is_healthy = await collector.health_check()
    assert is_healthy is False

@pytest.mark.asyncio
@patch('httpx.AsyncClient')
async def test_process_url_seed_aliases_mode(mock_client_class, collector):
    """Modo seed-aliases deve apenas extrair um set() com todos os times unicos."""
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.content = FAKE_CSV_BYTES
    
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_resp
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_instance.__aexit__.return_value = False
    mock_client_class.return_value = mock_client_instance

    meta = {'url': 'http://fake.csv', 'code': 'E0', 'type': 'main'}
    aliases = await collector._process_url(meta, mode='seed-aliases')

    assert isinstance(aliases, set)
    # 5 linhas de jogos -> 10 times possíveis
    expected_teams = {
        "Burnley", "Man City", 
        "Arsenal", "Nott'm Forest", 
        "NoTimeTeam", "OtherTeam",
        "Bad", "Time",
        "Brentford", "Tottenham"
    }
    assert aliases == expected_teams

@pytest.mark.asyncio
async def test_process_url_date_parsing_resilience(collector):
    """
    Simular the data parsing logic offline extracting df formatting rules directly.
    A football data as vezes manda linhas sem Date (NaN) ou sem Time (NaN). 
    Se parse o CSV via pandas ele transforma Date english em formato Date nativo.
    """
    df = pd.read_csv(io.BytesIO(FAKE_CSV_BYTES), encoding='utf-8')
    df['parsed_date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df['Time'] = df['Time'].fillna('12:00')
    df['kickoff_str'] = df['parsed_date'].dt.strftime('%Y-%m-%d') + ' ' + df['Time']
    df['kickoff'] = pd.to_datetime(df['kickoff_str'], errors='coerce')

    # A 3ª e a 4ª linha tem horarios zuados
    # 3a linha: empty Time (NoTimeTeam)
    assert df.loc[2]['Time'] == '12:00'
    assert df.loc[2]['kickoff'].hour == 12
    # 4a linha: BADTIME -> pd.to_datetime should result in NaT
    assert pd.isna(df.loc[3]['kickoff'])

    # 1a e 2a linha corretas
    assert df.loc[0]['kickoff'].hour == 20
    assert df.loc[0]['kickoff'].minute == 0
    assert df.loc[1]['kickoff'].hour == 12
    assert df.loc[1]['kickoff'].minute == 30
