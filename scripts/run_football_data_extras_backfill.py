"""
scripts/run_football_data_extras_backfill.py

Backfill de odds do football-data.co.uk APENAS para as 4 ligas "extra":
BRA_SA, AUT_BL, MEX_LM, SWI_SL
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collectors.football_data.csv_collector import FootballDataCollector


async def run():
    print("\n" + "=" * 55)
    print("  FOOTBALL-DATA — BACKFILL EXTRAS ONLY")
    print("  (BRA, AUT, MEX, SWZ)")
    print("=" * 55 + "\n")

    collector = FootballDataCollector()
    await collector._init_db_and_caches()

    # Filtra apenas as ligas extra
    original_config = collector._leagues_config.copy()
    extras_only = {
        k: v for k, v in original_config.items()
        if v.get("football_data_type") == "extra"
    }

    print(f"Ligas extra encontradas: {list(extras_only.keys())}")
    collector._leagues_config = extras_only

    result = await collector.collect(mode="backfill")

    print(f"\nResultado: {result.status.name}")
    print(f"Registros processados: {result.records_collected}")


if __name__ == "__main__":
    asyncio.run(run())
