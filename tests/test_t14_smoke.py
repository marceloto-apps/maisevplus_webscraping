import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.scheduler.jobs import (
    odds_standard,
    odds_gameday_hourly,
    schedule_gameday_jobs,
    odds_single_match,
    set_scheduler,
)

class FakeCollectResult:
    def __init__(self, records_collected=5):
        self.records_collected = records_collected

@pytest.mark.asyncio
async def test_odds_standard_calls_collector():
    """Verifica que odds_standard instancia OddsApiCollector com mode correto."""
    with patch("src.scheduler.jobs.OddsApiCollector") as MockCollector:
        instance = MockCollector.return_value
        instance.collect = AsyncMock(return_value=FakeCollectResult(records_collected=12))

        # Chama a função interna (sem o wrapper safe_job)
        result = await odds_standard.__wrapped__()

        MockCollector.assert_called_once()
        call_kwargs = instance.collect.call_args
        assert "validation" in str(call_kwargs)  # mode="validation"
        assert result["total"] == 12

@pytest.mark.asyncio
async def test_odds_gameday_hourly_calls_prematch():
    with patch("src.scheduler.jobs.OddsApiCollector") as MockCollector:
        instance = MockCollector.return_value
        instance.collect = AsyncMock(return_value=FakeCollectResult(records_collected=8))

        result = await odds_gameday_hourly.__wrapped__()
        assert "prematch" in str(instance.collect.call_args)
        assert result["total"] == 8

@pytest.mark.asyncio
async def test_odds_single_match_graceful_on_no_id():
    """Se o coletor retorna records_collected=0 (sem odds_api_id), o job não explode."""
    with patch("src.scheduler.jobs.OddsApiCollector") as MockCollector:
        instance = MockCollector.return_value
        instance.collect = AsyncMock(return_value=FakeCollectResult(records_collected=0))

        result = await odds_single_match.__wrapped__(
            match_id="550e8400-e29b-41d4-a716-446655440000",
            label="pre60_odds"
        )
        assert result["match_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert result["total"] == 0

@pytest.mark.asyncio
async def test_schedule_gameday_creates_triggers():
    """Simula v_today_matches com 2 jogos e verifica criação de DateTriggers."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Sao_Paulo")
    future = datetime.now(tz) + timedelta(hours=4)

    fake_rows = [
        {
            "match_id": "550e8400-e29b-41d4-a716-446655440000",
            "kickoff": future,
            "home_team": "Palmeiras",
            "away_team": "Santos",
        },
        {
            "match_id": "660e8400-e29b-41d4-a716-446655440001",
            "kickoff": future + timedelta(hours=2),
            "home_team": "Corinthians",
            "away_team": "São Paulo",
        },
    ]

    mock_scheduler = MagicMock()
    mock_scheduler.get_job.return_value = None  # Nenhum job duplicado
    set_scheduler(mock_scheduler)

    with patch("src.scheduler.jobs.get_pool") as mock_pool:
        # pool_instance is returned by 'await get_pool()', so get_pool() returns an async mock or coroutine,
        # mock_pool.return_value is what 'await' yields.
        pool_instance = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=fake_rows)
        # Setup async with pool.acquire()
        pool_instance.acquire.return_value.__aenter__.return_value = mock_conn
        mock_pool.return_value = pool_instance

        result = await schedule_gameday_jobs.__wrapped__()

    # 2 jogos × 4 triggers (lineups T-60, odds T-60, odds T-30, odds T-5) = 8 jobs criados
    assert mock_scheduler.add_job.call_count == 8
    assert result["matches_today"] == 2
    assert result["jobs_created"] == 8
