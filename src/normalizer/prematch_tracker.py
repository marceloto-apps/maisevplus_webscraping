from typing import Optional
from datetime import datetime, timezone
import math
from uuid import UUID

from src.normalizer.odds_normalizer import calculate_overround
from src.db.logger import get_logger

logger = get_logger(__name__)

def calculate_odd_period(kickoff: datetime, now: datetime) -> str:
    """
    Calcula a distância temporal entre o momento atual e o kickoff.
    Formato: "XXhYYm"
    """
    delta = kickoff - now
    total_minutes = int(delta.total_seconds() // 60)
    
    if total_minutes < 0:
        total_minutes = 0  # Previne tempos negativos virarem "0h-1m"
        
    horas = total_minutes // 60
    minutos = total_minutes % 60
    
    return f"{horas}h{minutos:02d}m"

async def insert_prematch_odds(
    *,
    conn,
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
    kickoff: datetime,
    time: datetime
) -> bool:
    """
    Insere na tabela prematch_odds calculando o odd_period e odd_moment localmente.
    Diferente de insert_odds_if_new, NÃO utiliza fingerprint SHA-256 para dedup.
    Todo snapshot é válido, pois o simple fato do tempo (odd_period) avançar sem as odds mudarem
    é uma sinalização de mercado (estabilidade).
    """
    if kickoff is None:
        logger.error(f"[prematch_odds] Match {match_id} sem kickoff informado. Skip.")
        return False
        
    # Calcula odd_period
    odd_period = calculate_odd_period(kickoff, time)
    
    # Calcula overround
    valid_odds = [v for v in [odds_1, odds_x, odds_2] if v is not None and v > 1.0]
    overround = calculate_overround(*valid_odds) if len(valid_odds) >= 2 else None

    # Determina odd_moment
    # opening -> se for o primeiro registro pra essa combo (match, bookmaker, market, line, period)
    # mid -> default
    is_opening = not await conn.fetchval(
        """
        SELECT EXISTS(
            SELECT 1 FROM prematch_odds 
            WHERE match_id = $1 
              AND bookmaker_id = $2 
              AND market_type = $3 
              AND line IS NOT DISTINCT FROM $4 
              AND period = $5
        )
        """,
        match_id, bookmaker_id, market_type, line, period
    )
    
    odd_moment = "opening" if is_opening else "mid"
    
    # Insert
    try:
        await conn.execute(
            """
            INSERT INTO prematch_odds (
                time, match_id, bookmaker_id, market_type, line, period,
                odds_1, odds_x, odds_2, overround, odd_period, odd_moment,
                source, collect_job_id
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
            )
            """,
            time, match_id, bookmaker_id, market_type, line, period,
            odds_1, odds_x, odds_2, overround, odd_period, odd_moment,
            source, collect_job_id
        )
        return True
    except Exception as e:
        logger.error(f"[prematch_odds] Erro de DB no insert: {e}")
        return False

async def fetch_eligible_prematch_matches(conn, phase: str):
    """
    Busca partidas que se encaixam na fase de tracking específica.
    """
    # tracking_daily: (D+3 a D+5) - kickoff_hours_from_now BETWEEN 72 AND 120
    # tracking_4h: (D+1 a D+2) - kickoff_hours_from_now BETWEEN 24 AND 72
    # tracking_2h: (D-0, > 35min away) - kickoff_hours_from_now BETWEEN 0.58 AND 24
    
    if phase == "tracking_daily":
        min_hours, max_hours = 72, 144
    elif phase == "tracking_4h":
        min_hours, max_hours = 24, 72
    elif phase == "tracking_2h":
        min_hours, max_hours = 0.58, 24
    elif phase == "tracking_2x":
        min_hours, max_hours = 2, 120
    elif phase in ("pre30", "pre2"):
        min_hours, max_hours = 0, 0.58
    else:
        min_hours, max_hours = 0, 240
        
    rows = await conn.fetch(
        '''
        SELECT match_id, flashscore_id, kickoff
        FROM matches 
        WHERE status = 'scheduled' 
          AND flashscore_id IS NOT NULL
          AND kickoff > now() + interval '1 hour' * $1
          AND kickoff <= now() + interval '1 hour' * $2
        ''',
        min_hours, max_hours
    )
    
    return [{"match_id": r['match_id'], "flashscore_id": r['flashscore_id'], "kickoff": r['kickoff']} for r in rows]

