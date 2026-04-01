"""
T03 — src/tests/test_dedup.py
Testes unitários para dedup.py — partes que não dependem de banco.
insert_odds_if_new() é testado com mock de conexão asyncpg.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.normalizer.dedup import compute_content_hash, insert_odds_if_new
from uuid import UUID
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# compute_content_hash
# ---------------------------------------------------------------------------

class TestComputeContentHash:
    BASE = dict(
        match_id="550e8400-e29b-41d4-a716-446655440000",
        bookmaker_id=1,
        market_type="1x2",
        line=None,
        period="ft",
        odds={"odds_1": 1.95, "odds_x": 3.4, "odds_2": 4.2},
    )

    def test_returns_64_char_hex(self):
        h = compute_content_hash(**self.BASE)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        h1 = compute_content_hash(**self.BASE)
        h2 = compute_content_hash(**self.BASE)
        assert h1 == h2

    def test_different_odds_produce_different_hash(self):
        other = {**self.BASE, "odds": {"odds_1": 2.0, "odds_x": 3.4, "odds_2": 4.2}}
        assert compute_content_hash(**self.BASE) != compute_content_hash(**other)

    def test_different_market_produces_different_hash(self):
        other = {**self.BASE, "market_type": "ou"}
        assert compute_content_hash(**self.BASE) != compute_content_hash(**other)

    def test_odds_order_invariant(self):
        # A ordem das chaves no dict de odds não deve alterar o hash
        a = {**self.BASE, "odds": {"odds_1": 1.95, "odds_x": 3.4}}
        b = {**self.BASE, "odds": {"odds_x": 3.4, "odds_1": 1.95}}
        assert compute_content_hash(**a) == compute_content_hash(**b)

    def test_with_line(self):
        with_line    = {**self.BASE, "market_type": "ou", "line": 2.5}
        without_line = {**self.BASE, "market_type": "ou", "line": None}
        assert compute_content_hash(**with_line) != compute_content_hash(**without_line)


# ---------------------------------------------------------------------------
# insert_odds_if_new — mock de conexão asyncpg
# ---------------------------------------------------------------------------

MATCH_ID    = UUID("550e8400-e29b-41d4-a716-446655440000")
SAMPLE_TIME = datetime(2025, 3, 29, 15, 0, tzinfo=timezone.utc)


def _make_conn(last_hash: str | None):
    """Cria um mock de conexão asyncpg que retorna last_hash na query de verificação."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=last_hash)
    conn.execute  = AsyncMock(return_value="INSERT 0 1")
    return conn


@pytest.mark.asyncio
async def test_insert_when_no_previous_hash():
    conn = _make_conn(last_hash=None)
    inserted = await insert_odds_if_new(
        conn=conn,
        match_id=MATCH_ID, bookmaker_id=1, market_type="1x2",
        line=None, period="ft",
        odds_1=1.95, odds_x=3.4, odds_2=4.2,
        source="flashscore", collect_job_id="job_001",
        is_opening=True, time=SAMPLE_TIME,
    )
    assert inserted is True
    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_skip_when_hash_matches():
    # Pré-calcula o hash que seria gerado
    expected_hash = compute_content_hash(
        str(MATCH_ID), 1, "1x2", None, "ft",
        {"odds_1": "1.95", "odds_x": "3.4", "odds_2": "4.2"},
    )
    conn = _make_conn(last_hash=expected_hash)
    inserted = await insert_odds_if_new(
        conn=conn,
        match_id=MATCH_ID, bookmaker_id=1, market_type="1x2",
        line=None, period="ft",
        odds_1=1.95, odds_x=3.4, odds_2=4.2,
        source="flashscore", collect_job_id="job_001",
        is_opening=False, time=SAMPLE_TIME,
    )
    assert inserted is False
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_insert_when_odds_changed():
    # Hash existe mas com odds diferentes → deve inserir
    old_hash = compute_content_hash(
        str(MATCH_ID), 1, "1x2", None, "ft",
        {"odds_1": "1.80", "odds_x": "3.4", "odds_2": "4.2"},  # odds antigas
    )
    conn = _make_conn(last_hash=old_hash)
    inserted = await insert_odds_if_new(
        conn=conn,
        match_id=MATCH_ID, bookmaker_id=1, market_type="1x2",
        line=None, period="ft",
        odds_1=1.95,  # odds DIFERENTES das anteriores
        odds_x=3.4, odds_2=4.2,
        source="flashscore", collect_job_id="job_002",
        is_opening=False, time=SAMPLE_TIME,
    )
    assert inserted is True
