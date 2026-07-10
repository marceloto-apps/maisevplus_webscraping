import asyncio
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.db.pool import get_pool
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector, CollectionMetrics

load_dotenv()

async def main():
    pool = await get_pool()
    match_id = "33d4831d-5ac4-4dd3-b3e5-dfa62f900f66"
    flashscore_id = "863eg7q9"
    kickoff = datetime(2021, 8, 13, 19, 0, tzinfo=timezone.utc)
    
    print(f"Limpando registros anteriores do match {flashscore_id} para o teste...")
    async with pool.acquire() as conn:
        # Deleta registros antigos de abertura para este match
        del_odds = await conn.execute("""
            DELETE FROM odds_history 
            WHERE match_id = $1 AND is_opening = TRUE
        """, match_id)
        print(f"Odds de abertura deletadas: {del_odds}")
        
        # Deleta log antigo do retrofit para este match
        del_log = await conn.execute("""
            DELETE FROM retrofit_match_log
            WHERE match_id = $1
        """, match_id)
        print(f"Logs de retrofit deletados: {del_log}")

    print("\nIniciando coletor virtual de odds...")
    collector = FlashscoreOddsCollector(markets=["1x2_ft", "ou_ft", "ah_ft"])
    job_id = collector.generate_job_id("flashscore_retrofit_test")
    metrics = CollectionMetrics()
    
    async with AsyncCamoufox(headless=True) as browser:
        async with pool.acquire() as conn:
            try:
                # Executa a coleta real que grava no DB
                result = await collector.collect_match(
                    browser, conn, match_id, flashscore_id,
                    is_closing=False, job_id=job_id, metrics=metrics,
                    is_prematch=False, kickoff=kickoff, skip_stats=True,
                    skip_closing=True
                )
                print(f"\nResultado da execução do collector: {result}")
            except Exception as e:
                print(f"\nErro durante execução do collector: {e}")
                
            # Verifica se gravou
            has_opening = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM odds_history
                    WHERE match_id = $1 AND is_opening = TRUE
                )
            """, match_id)
            print(f"Existe registro is_opening = TRUE no DB para este match? {has_opening}")
            
            if has_opening:
                rows = await conn.fetch("""
                    SELECT bookmaker_id, market_type, period, odds_1, odds_x, odds_2, time
                    FROM odds_history
                    WHERE match_id = $1 AND is_opening = TRUE
                """, match_id)
                print("\nOdds de abertura gravadas:")
                for r in rows:
                    print(dict(r))
            else:
                # Se não gravou, vamos ver se existe algum registro de odds geral para este match
                any_odds = await conn.fetch("""
                    SELECT bookmaker_id, market_type, is_opening, is_closing, count(*)
                    FROM odds_history
                    WHERE match_id = $1
                    GROUP BY bookmaker_id, market_type, is_opening, is_closing
                """, match_id)
                print("\nOutros registros de odds para este match no DB:")
                for r in any_odds:
                    print(dict(r))

if __name__ == "__main__":
    asyncio.run(main())
