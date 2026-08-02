import asyncio
import argparse
import os
import sys

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db.logger import configure_logging, get_logger

configure_logging()
logger = get_logger("reset_retrofit_log")

async def reset_matches(league_id: int = None, reset_all_no_opening: bool = False, since_date: str = "2026-07-30"):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if reset_all_no_opening:
            res = await conn.execute("DELETE FROM retrofit_match_log WHERE status = 'no_opening'")
            logger.info(f"Reset global concluído: {res} registros 'no_opening' removidos de retrofit_match_log.")
        elif league_id:
            res = await conn.execute("""
                DELETE FROM retrofit_match_log
                WHERE match_id IN (SELECT match_id FROM matches WHERE league_id = $1)
            """, league_id)
            logger.info(f"Reset da liga {league_id} concluído: {res} registros removidos de retrofit_match_log.")
        else:
            from datetime import datetime, timezone
            dt = datetime.strptime(since_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            res = await conn.execute("""
                DELETE FROM retrofit_match_log
                WHERE status = 'no_opening' AND processed_at >= $1
            """, dt)
            logger.info(f"Reset concluído: {res} registros 'no_opening' desde {since_date} removidos de retrofit_match_log.")

        # Recalcular processed_matches e ressetar ligas travadas ou erroneamente completadas
        await conn.execute("""
            UPDATE retrofit_queue rq
            SET status = CASE WHEN status = 'completed' AND (
                    SELECT COUNT(*) FROM matches m
                    WHERE m.league_id = rq.league_id AND m.flashscore_id IS NOT NULL
                      AND NOT EXISTS (SELECT 1 FROM odds_history o WHERE o.match_id = m.match_id AND o.is_opening = TRUE)
                      AND NOT EXISTS (SELECT 1 FROM retrofit_match_log l WHERE l.match_id = m.match_id AND l.status = 'no_opening')
                ) > 0 THEN 'pending' ELSE rq.status END,
                processed_matches = (
                    SELECT COUNT(*) FROM retrofit_match_log l
                    JOIN matches m ON m.match_id = l.match_id
                    WHERE m.league_id = rq.league_id
                ),
                attempts = 0
        """)
        logger.info("Sincronização de status da retrofit_queue concluída.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset de logs de partidas no retrofit_match_log")
    parser.add_argument("--league-id", type=int, default=None, help="ID da liga para limpar logs")
    parser.add_argument("--all", action="store_true", default=False, help="Limpar todos os registros 'no_opening'")
    args = parser.parse_args()

    asyncio.run(reset_matches(league_id=args.league_id, reset_all_no_opening=args.all))
