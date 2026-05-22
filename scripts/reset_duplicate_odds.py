import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db.logger import configure_logging, get_logger

configure_logging()
logger = get_logger("reset_duplicate_odds")

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Identificar partidas com odds HT/FT de O/U idênticas coletadas desde 2026-05-20
        logger.info("Buscando partidas afetadas com odds HT/FT idênticas desde 2026-05-20...")
        rows = await conn.fetch("""
            SELECT DISTINCT oh1.match_id, m.flashscore_id, m.kickoff
            FROM odds_history oh1
            JOIN odds_history oh2 ON oh1.match_id = oh2.match_id 
                                 AND oh1.bookmaker_id = oh2.bookmaker_id 
                                 AND oh1.market_type = oh2.market_type
                                 AND oh1.line = oh2.line
            JOIN matches m ON oh1.match_id = m.match_id
            WHERE oh1.market_type = 'ou'
              AND oh1.period = 'ht'
              AND oh2.period = 'ft'
              AND oh1.odds_1 = oh2.odds_1
              AND oh1.odds_2 = oh2.odds_2
              AND oh1.time >= '2026-05-20 00:00:00+00'
        """)
        
        if not rows:
            logger.info("Nenhuma partida com odds HT/FT idênticas encontrada no banco de dados.")
            return

        match_ids = [r["match_id"] for r in rows]
        logger.info(f"Encontradas {len(rows)} partidas afetadas:")
        for r in rows:
            logger.info(f"  - Flashscore ID: {r['flashscore_id']} | Match ID: {r['match_id']} | Kickoff: {r['kickoff']}")

        async with conn.transaction():
            # 2. Deletar os registros incorretos de 'ht' para as partidas identificadas
            logger.info("Deletando odds incorretas de 'ht' da tabela odds_history...")
            delete_res = await conn.execute("""
                DELETE FROM odds_history
                WHERE market_type = 'ou'
                  AND period = 'ht'
                  AND time >= '2026-05-20 00:00:00+00'
                  AND match_id = ANY($1)
            """, match_ids)
            logger.info(f"  -> Resultado: {delete_res}")

            # 3. Resetar o status na fila fc_complementary_queue
            logger.info("Resetando status e tentativas na fc_complementary_queue...")
            queue_res = await conn.execute("""
                UPDATE fc_complementary_queue
                SET status = 'pending',
                    attempts = 0,
                    failed_markets = ARRAY['ou_ht']::varchar[],
                    processed_at = NULL
                WHERE match_id = ANY($1)
            """, match_ids)
            logger.info(f"  -> Resultado: {queue_res}")

            # 4. Resetar a flag scraping_flashscore na tabela matches principal
            logger.info("Resetando scraping_flashscore na tabela matches...")
            matches_res = await conn.execute("""
                UPDATE matches
                SET scraping_flashscore = false
                WHERE match_id = ANY($1)
            """, match_ids)
            logger.info(f"  -> Resultado: {matches_res}")

        logger.info("Limpeza e reset concluídos com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
