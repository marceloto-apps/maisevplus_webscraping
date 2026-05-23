"""
scripts/run_daily_update.py

Roda manualmente os jobs diários de atualização de resultados:
  1. football_data_daily  — atualiza status/placar via CSVs da football-data.co.uk
  2. footystats_daily     — atualiza status/placar via API da FootyStats

Uso:
  python scripts/run_daily_update.py
  python scripts/run_daily_update.py --only football_data
  python scripts/run_daily_update.py --only footystats
"""

import asyncio
import sys
import os
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run_football_data():
    from src.collectors.football_data.csv_collector import FootballDataCollector
    print("\n[1/2] football_data_daily — baixando e processando CSVs...")
    t0 = time.monotonic()
    collector = FootballDataCollector()
    result = await collector.collect(mode="daily-update")
    elapsed = time.monotonic() - t0
    print(f"      Status    : {result.status.name}")
    print(f"      Processados: {result.records_collected} matches")
    print(f"      Tempo     : {elapsed:.1f}s")
    return result


async def run_footystats():
    from src.collectors.footystats.daily_updater import FootyStatsDailyUpdater
    print("\n[2/2] footystats_daily — atualizando via API FootyStats...")
    t0 = time.monotonic()
    updater = FootyStatsDailyUpdater()
    result = await updater.run()
    elapsed = time.monotonic() - t0
    print(f"      Seasons processadas: {result.get('seasons_processed', '?')}")
    print(f"      Matches upserted  : {result.get('matches_upserted', '?')}")
    print(f"      Seasons fechadas  : {result.get('seasons_closed', '?')}")
    print(f"      Tempo             : {elapsed:.1f}s")
    return result


async def main():
    parser = argparse.ArgumentParser(description="Roda jobs diários de atualização de resultados")
    parser.add_argument(
        "--only",
        choices=["football_data", "footystats"],
        help="Roda somente um dos dois jobs"
    )
    args = parser.parse_args()

    print("=" * 65)
    print("  DAILY UPDATE MANUAL RUN")
    print("=" * 65)

    t_total = time.monotonic()

    if args.only == "footystats":
        await run_footystats()
    elif args.only == "football_data":
        await run_football_data()
    else:
        await run_football_data()
        await run_footystats()

    elapsed_total = time.monotonic() - t_total
    print(f"\n{'=' * 65}")
    print(f"  Concluído em {elapsed_total:.1f}s")
    print(f"  Verifique os stale com:")
    print(f"  SELECT COUNT(*) FROM matches WHERE kickoff < NOW() AND status = 'scheduled';")
    print(f"{'=' * 65}\n")


if __name__ == "__main__":
    asyncio.run(main())
