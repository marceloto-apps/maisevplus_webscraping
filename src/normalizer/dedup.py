"""
T03 — src/normalizer/dedup.py

Deduplicação de odds — duas camadas conforme SPECS §8.6:

  Camada 1 (aplicação): insert_odds_if_new() busca o último content_hash
    da mesma combinação (match + bookmaker + market + line + period).
    Se idêntico → skip sem gastar um round-trip de write no DB.

  Camada 2 (banco): idx_odds_dedup é um UNIQUE INDEX sobre
    (match_id, bookmaker_id, market_type, line, period, content_hash, time).
    Garante integridade mesmo em workers paralelos que passem na Camada 1
    antes de qualquer deles completar o INSERT.
"""

import hashlib
import json
from typing import Any, Optional
from uuid import UUID

from .odds_normalizer import calculate_overround
from ..db import execute, fetch_val


def compute_content_hash(
    match_id: str,
    bookmaker_id: int,
    market_type: str,
    line: Optional[float],
    period: str,
    odds: dict[str, Any],
) -> str:
    """
    Gera um fingerprint SHA-256 de 64 chars determinístico para um snapshot
    de odds. Entradas idênticas sempre produzem o mesmo hash.

    Args:
        match_id:     UUID do jogo (string)
        bookmaker_id: ID da casa de apostas
        market_type:  ex. '1x2', 'ou', 'ah'
        line:         linha do mercado (ex: 2.5) ou None
        period:       'ft' | 'ht'
        odds:         dict de valores, ex. {'odds_1': 1.95, 'odds_x': 3.4, 'odds_2': 4.2}

    Returns:
        str: hash hexadecimal de 64 caracteres
    """
    payload = {
        "match_id":    str(match_id),
        "bookmaker_id": bookmaker_id,
        "market_type": market_type,
        "line":        line,
        "period":      period,
        "odds":        {k: str(v) for k, v in sorted(odds.items())},
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


async def insert_odds_if_new(
    *,
    conn,               # asyncpg connection/transaction
    match_id: UUID,
    bookmaker_id: int,
    market_type: str,
    line: Optional[float],
    period: str,
    odds_1: Optional[float],
    odds_x: Optional[float],
    odds_2: Optional[float],
    source: str,
    collect_job_id: str,
    is_opening: bool = False,
    time,               # datetime aware (UTC)
) -> bool:
    """
    Camada 1 de dedup: verifica o último content_hash antes de inserir.
    Retorna True se inseriu, False se era duplicata.

    A Camada 2 (ON CONFLICT no UNIQUE INDEX via INSERT ... ON CONFLICT DO NOTHING)
    garante integridade caso dois workers passem na Camada 1 simultaneamente.
    """
    # Monta o dict de odds passadas (ignora None para o hash)
    odds_vals = {k: v for k, v in
                 [("odds_1", odds_1), ("odds_x", odds_x), ("odds_2", odds_2)]
                 if v is not None}

    content_hash = compute_content_hash(
        str(match_id), bookmaker_id, market_type, line, period, odds_vals
    )

    # --- Camada 1: verificar último hash ---
    last_hash = await conn.fetchval(
        """
        SELECT content_hash
        FROM odds_history
        WHERE match_id = $1
          AND bookmaker_id = $2
          AND market_type  = $3
          AND COALESCE(line, 0) = COALESCE($4, 0)
          AND period = $5
        ORDER BY time DESC
        LIMIT 1
        """,
        match_id, bookmaker_id, market_type, line, period,
    )
    if last_hash == content_hash:
        return False   # duplicata — skip

    # Calcula overround apenas quando tem pelo menos 2 odds
    valid_odds = [v for v in [odds_1, odds_x, odds_2] if v is not None and v > 1.0]
    overround = calculate_overround(*valid_odds) if len(valid_odds) >= 2 else None

    # --- Camada 2 via ON CONFLICT DO NOTHING (safety net para workers paralelos) ---
    await conn.execute(
        """
        INSERT INTO odds_history
            (time, match_id, bookmaker_id, market_type, line, period,
             odds_1, odds_x, odds_2, overround,
             is_opening, is_closing, source, collect_job_id, content_hash)
        VALUES
            ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, FALSE, $12, $13, $14)
        ON CONFLICT (match_id, bookmaker_id, market_type,
                     COALESCE(line, 0), period, content_hash, time)
        DO NOTHING
        """,
        time, match_id, bookmaker_id, market_type, line, period,
        odds_1, odds_x, odds_2, overround,
        is_opening, source, collect_job_id, content_hash,
    )
    return True
