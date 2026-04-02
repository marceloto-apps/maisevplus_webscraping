import pytest
import asyncio
from unittest.mock import patch, MagicMock
from uuid import uuid4

from src.collectors.api_football.api_collector import ApiFootballCollector
from src.collectors.base import CollectStatus

@pytest.mark.asyncio
async def test_api_football_empty_lineup_retry():
    collector = ApiFootballCollector()
    
    with patch("src.db.pool.get_pool") as mock_pool:
        conn = MagicMock()
        mock_pool.return_value.acquire.return_value.__aenter__.return_value = conn
        
        # Simulando match existente no DB
        match_id = uuid4()
        conn.fetchrow.return_value = {
            "api_football_id": "12345",
            "league_id": 1,
            "home_team_id": 1,
            "away_team_id": 2,
            "date": "2025-01-01"
        }
        
        with patch.object(collector, "_fetch") as mock_fetch:
            with patch("src.collectors.api_football.api_collector.KeyManager.get_key") as mock_key:
                mock_key.return_value = "token"
                # Mock empty lineups
                mock_fetch.return_value = {"response": []}
                
                result = await collector.collect_lineups(match_id)
                assert result.status == CollectStatus.PARTIAL
                assert result.records_collected == 0

@pytest.mark.asyncio
async def test_api_football_health():
    collector = ApiFootballCollector()
    with patch("src.collectors.api_football.api_collector.KeyManager.get_key") as mock_key:
        mock_key.return_value = "token"
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp
            health = await collector.health_check()
            assert health is True
