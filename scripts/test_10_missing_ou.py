"""
scripts/test_10_missing_ou.py

A diagnostic test script to select 10 matches that are missing Over/Under odds
in the database, run the updated FlashscoreOddsCollector on them, and insert the odds.
"""
import asyncio
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector, CollectionMetrics
from src.db.logger import configure_logging, get_logger
from src.db.pool import get_pool

configure_logging()
logger = get_logger("test_10_missing_ou")

async def get_test_matches(pool):
    async with pool.acquire() as conn:
        # Tenta pegar da fila complementar primeiro
        logger.info("Buscando partidas candidatas na fc_complementary_queue...")
        rows = await conn.fetch("""
            SELECT match_id, flashscore_id, kickoff, failed_markets 
            FROM fc_complementary_queue
            WHERE status != 'completed' 
              AND (failed_markets IS NULL OR failed_markets @> ARRAY['ou_ft'] OR failed_markets @> ARRAY['ou_ht'])
            ORDER BY kickoff DESC
            LIMIT 10;
        """)
        
        matches = []
        for r in rows:
            matches.append({
                "match_id": r["match_id"],
                "flashscore_id": r["flashscore_id"],
                "kickoff": r["kickoff"],
                "source": "fc_complementary_queue"
            })
            
        # Se achou menos que 10, busca no banco geral de matches + odds_history
        needed = 10 - len(matches)
        if needed > 0:
            logger.info(f"Fila complementar retornou {len(matches)} partidas. Buscando mais {needed} partidas no banco geral...")
            exclude_ids = [m["match_id"] for m in matches]
            
            general_rows = await conn.fetch("""
                SELECT DISTINCT m.match_id, m.flashscore_id, m.kickoff
                FROM matches m
                JOIN odds_history oh ON m.match_id = oh.match_id
                WHERE m.flashscore_id IS NOT NULL
                  AND m.match_id NOT IN (SELECT match_id FROM fc_complementary_queue WHERE status = 'completed')
                  AND ($1::uuid[] IS NULL OR NOT (m.match_id = ANY($1)))
                  AND NOT EXISTS (
                      SELECT 1 FROM odds_history oh2
                      WHERE oh2.match_id = m.match_id
                        AND oh2.market_type = 'ou'
                  )
                ORDER BY m.kickoff DESC
                LIMIT $2;
            """, exclude_ids if exclude_ids else None, needed)
            
            for r in general_rows:
                matches.append({
                    "match_id": r["match_id"],
                    "flashscore_id": r["flashscore_id"],
                    "kickoff": r["kickoff"],
                    "source": "general_db"
                })
                
        return matches

async def main():
    pool = await get_pool()
    try:
        matches = await get_test_matches(pool)
        if not matches:
            logger.warning("Nenhuma partida elegível encontrada sem Over/Under no banco de dados!")
            return
            
        logger.info(f"Encontradas {len(matches)} partidas para o teste:")
        for idx, m in enumerate(matches):
            logger.info(f"  [{idx+1}] ID: {m['match_id']} | Flashscore: {m['flashscore_id']} | Kickoff: {m['kickoff']} | Origem: {m['source']}")
            
        # Inicializa o Camoufox
        metrics = CollectionMetrics()
        collector = FlashscoreOddsCollector(markets=["ou_ft", "ou_ht"])
        
        logger.info("\nIniciando raspagem de Over/Under...")
        async with AsyncCamoufox(headless=True, enable_cache=True) as browser:
            for idx, m in enumerate(matches):
                logger.info(f"\n--- Processando {idx+1}/{len(matches)}: Match {m['flashscore_id']} ---")
                
                async with pool.acquire() as conn:
                    try:
                        metrics.total_processed += 1
                        result = await collector.collect_match(
                            browser, conn,
                            match_id_uuid=str(m["match_id"]),
                            flashscore_id=m["flashscore_id"],
                            is_closing=False,
                            job_id="test_missing_ou_run",
                            metrics=metrics,
                            kickoff=m["kickoff"],
                            skip_stats=True  # foca apenas em odds de OU
                        )
                        
                        logger.info(f"Resultado do Match {m['flashscore_id']}:")
                        logger.info(f"  Total Inserido: {result['total_inserted']} odds")
                        logger.info(f"  Mercados Coletados: {result['markets_collected']}")
                        logger.info(f"  Mercados Falhos: {result['markets_failed']}")
                        logger.info(f"  Completo (1X2 + OU)? {'Sim' if result['is_complete'] else 'Não'}")
                        
                        # Atualiza na fila se for dessa origem
                        if m["source"] == "fc_complementary_queue":
                            if result["is_complete"] or "ou_ft" in result["markets_collected"]:
                                await conn.execute("""
                                    UPDATE fc_complementary_queue 
                                    SET status = 'completed', attempts = attempts + 1, processed_at = NOW(), failed_markets = '{}'
                                    WHERE match_id = $1
                                """, m["match_id"])
                                await conn.execute("UPDATE matches SET scraping_flashscore = true WHERE match_id = $1", m["match_id"])
                                logger.info(f"  -> Fila complementar e matches atualizados para concluído.")
                                
                    except Exception as e:
                        logger.error(f"Erro na raspagem do match {m['flashscore_id']}: {e}")
                        
                await asyncio.sleep(2)
                
        logger.info("\n" + "="*40)
        logger.info("FIM DO TESTE DE OVER/UNDER")
        logger.info(f"Partidas processadas: {metrics.total_processed}")
        logger.info(f"Partidas com odds coletadas: {metrics.with_odds}")
        logger.info("="*40)
        
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
