import pytest
import asyncio
from unittest.mock import patch

from src.scheduler.key_manager import KeyManager, NoKeysAvailableError

@pytest.mark.asyncio
async def test_key_manager_get_key_success():
    with patch("src.db.helpers.fetch_one") as mock_fetch:
        mock_fetch.return_value = {
            "id": 1,
            "key_value": "dummy-key",
            "limit_daily": 100,
            "limit_monthly": 500
        }
        
        with patch("src.db.helpers.execute") as mock_execute:
            key = await KeyManager.get_key("test_service")
            assert key == "dummy-key"
            mock_execute.assert_called_once()

@pytest.mark.asyncio
async def test_key_manager_no_keys():
    with patch("src.db.helpers.fetch_one") as mock_fetch:
        mock_fetch.return_value = None
        
        with pytest.raises(NoKeysAvailableError):
            await KeyManager.get_key("test_service")
