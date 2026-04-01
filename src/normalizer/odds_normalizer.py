"""
T03 — src/normalizer/odds_normalizer.py
Funções matemáticas de normalização de odds.
"""

from typing import Sequence


def calculate_overround(*odds: float) -> float:
    """
    Calcula o overround (margem da casa de apostas) dado um conjunto de odd
    decimais para todos os resultados de um mercado.

    Fórmula: sum(1/odd_i) - 1.0
    Valores positivos = margem favorável à casa; 0 = mercado justo.

    Exemplos:
        1x2: calculate_overround(1.90, 3.50, 4.00) ≈ 0.0406 (4.06%)
        OU:  calculate_overround(1.87, 1.97)        ≈ 0.0371 (3.71%)
    """
    if not odds:
        raise ValueError("Ao menos uma odd deve ser fornecida")
    for o in odds:
        if o <= 1.0:
            raise ValueError(f"Odd inválida: {o}. Deve ser > 1.0")
    return round(sum(1.0 / o for o in odds) - 1.0, 6)


def to_implied_probability(odd: float) -> float:
    """Converte odd decimal em probabilidade implícita bruta (sem deducao do overround)."""
    if odd <= 1.0:
        raise ValueError(f"Odd inválida: {odd}")
    return round(1.0 / odd, 6)


def fair_odds_from_probs(probs: Sequence[float]) -> list[float]:
    """
    Dado um conjunto de probabilidades reais (sum=1.0), retorna as odds justas.
    Útil para comparar com odds de mercado e calcular edge.

    Ex: fair_odds_from_probs([0.50, 0.25, 0.25]) → [2.0, 4.0, 4.0]
    """
    for p in probs:
        if not (0.0 < p < 1.0):
            raise ValueError(f"Probabilidade inválida: {p}")
    total = sum(probs)
    if not (0.99 <= total <= 1.01):
        raise ValueError(f"Probabilidades devem somar ~1.0, soma atual: {total}")
    return [round(1.0 / p, 4) for p in probs]
