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

async def reset_matches(league_id: int = None, reset_all_no_opening: bool = False):
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
            # Por padrão limpa as últimas partidas testadas recentemente
            res = await conn.execute("""
                DELETE FROM retrofit_match_log
                WHERE processed_at >= NOW() - INTERVAL '1 day'
            """)
            logger.info(f"Reset padrão concluído: {res} registros das últimas 24h removidos de retrofit_match_log.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset de logs de partidas no retrofit_match_log")
    parser.add_argument("--league-id", type=int, default=None, help="ID da liga para limpar logs")
    parser.add_argument("--all", action="store_true", default=False, help="Limpar todos os registros 'no_opening'")
    args = parser.parse_args()

    asyncio.run(reset_matches(league_id=args.league_id, reset_all_no_opening=args.all))
