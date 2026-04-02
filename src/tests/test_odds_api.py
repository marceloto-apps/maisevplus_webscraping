import pytest
import asyncio
from unittest.mock import patch, MagicMock

from src.collectors.odds_api.api_collector import OddsApiCollector
from src.collectors.base import CollectStatus
from src.scheduler.key_manager import NoKeysAvailableError

@pytest.mark.asyncio
async def test_odds_api_get_budget_tier():
    collector = OddsApiCollector()
    
    with patch("src.collectors.odds_api.api_collector.KeyManager.get_service_budget") as mock_budget:
        # Full budget (tier 1)
        mock_budget.return_value = {"total_limit_monthly": 2500, "total_usage_month": 0}
        tier = await collector._get_budget_tier()
        assert tier == 1
        
        # Low budget (tier 2)
        mock_budget.return_value = {"total_limit_monthly": 2500, "total_usage_month": 2100}
        tier = await collector._get_budget_tier()
        assert tier == 2
        
        # Critical budget (tier 3)
        mock_budget.return_value = {"total_limit_monthly": 2500, "total_usage_month": 2400}
        tier = await collector._get_budget_tier()
        assert tier == 3

@pytest.mark.asyncio
async def test_odds_api_no_keys():
    collector = OddsApiCollector()
    collector.leagues_config = {"ENG_PL": {"odds_api_sport_key": "soccer_epl", "tier": 1}}
    
    with patch("src.collectors.odds_api.api_collector.KeyManager.get_key") as mock_key:
        mock_key.side_effect = NoKeysAvailableError("No keys")
        with patch.object(collector, "_get_budget_tier", return_value=1):
            with patch("src.db.pool.get_pool") as mock_pool:
                # Mock connection
                conn = MagicMock()
                mock_pool.return_value.acquire.return_value.__aenter__.return_value = conn
                
                result = await collector.collect(mode="validation")
                # Because there was a NoKeysAvailableError, parsing will fail before collecting anything.
                # However, our collect returns FAILED if all targets failed.
                assert result.status == CollectStatus.FAILED
                assert "No keys" in result.errors[0]
