"""
T03 — src/tests/test_normalizer.py
Testes unitários para odds_normalizer.py e team_resolver.py (partes puras).
Roda sem banco: sem fixtures de DB, sem asyncpg.
"""

import pytest
from src.normalizer.odds_normalizer import (
    calculate_overround,
    to_implied_probability,
    fair_odds_from_probs,
)


# ---------------------------------------------------------------------------
# calculate_overround
# ---------------------------------------------------------------------------

class TestCalculateOverround:
    def test_1x2_typical(self):
        # Pinnacle-like 1X2 market
        overround = calculate_overround(1.90, 3.50, 4.00)
        # 1/1.90 + 1/3.50 + 1/4.00 = 0.5263 + 0.2857 + 0.25 = 1.062 → overround ~0.062
        assert 0.05 < overround < 0.08

    def test_ou_market(self):
        overround = calculate_overround(1.87, 1.97)
        # 1/1.87 + 1/1.97 ≈ 0.5348 + 0.5076 = 1.0424 → ~0.042
        assert 0.03 < overround < 0.06

    def test_fair_market_returns_zero(self):
        # Odds exatamente justas (sem margem)
        overround = calculate_overround(2.0, 2.0)
        assert overround == pytest.approx(0.0, abs=1e-6)

    def test_single_odd_raises(self):
        with pytest.raises(ValueError, match="Ao menos uma odd"):
            calculate_overround()

    def test_odd_below_or_equal_one_raises(self):
        with pytest.raises(ValueError):
            calculate_overround(1.95, 1.0)

    def test_deterministic(self):
        assert calculate_overround(1.95, 3.4, 4.2) == calculate_overround(1.95, 3.4, 4.2)

    def test_order_invariant(self):
        # Overround não depende da ordem das odds
        assert calculate_overround(1.90, 3.50, 4.00) == calculate_overround(4.00, 1.90, 3.50)


# ---------------------------------------------------------------------------
# to_implied_probability
# ---------------------------------------------------------------------------

class TestImpliedProbability:
    def test_even_money(self):
        assert to_implied_probability(2.0) == pytest.approx(0.5, abs=1e-5)

    def test_short_favourite(self):
        prob = to_implied_probability(1.20)
        assert prob == pytest.approx(1 / 1.20, abs=1e-5)

    def test_invalid_odd_raises(self):
        with pytest.raises(ValueError):
            to_implied_probability(0.95)


# ---------------------------------------------------------------------------
# fair_odds_from_probs
# ---------------------------------------------------------------------------

class TestFairOdds:
    def test_balanced_1x2(self):
        odds = fair_odds_from_probs([0.5, 0.25, 0.25])
        assert odds == [2.0, 4.0, 4.0]

    def test_probs_not_summing_to_one_raises(self):
        with pytest.raises(ValueError, match="Probabilidades devem somar"):
            fair_odds_from_probs([0.5, 0.5, 0.5])

    def test_invalid_prob_raises(self):
        with pytest.raises(ValueError):
            fair_odds_from_probs([0.0, 1.0])
