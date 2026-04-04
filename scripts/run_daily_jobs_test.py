"""
Script de teste manual dos dois jobs diários.
Uso:
    python scripts/run_daily_jobs_test.py --job footystats
    python scripts/run_daily_jobs_test.py --job football_data
    python scripts/run_daily_jobs_test.py --job both
"""
import asyncio
import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_footystats():
    from src.collectors.footystats.daily_updater import FootyStatsDailyUpdater
    print("=== FootyStats Daily Updater ===")
    updater = FootyStatsDailyUpdater()
    result = await updater.run()
    print(f"\n✓ Resultado:")
    print(f"  Temporadas processadas : {result['seasons_processed']}")
    print(f"  Matches upserted       : {result['matches_upserted']}")
    print(f"  Temporadas fechadas    : {result['seasons_closed']}")


async def test_football_data():
    from src.collectors.football_data.csv_collector import FootballDataCollector
    print("=== Football-Data Daily Update ===")
    collector = FootballDataCollector()
    result = await collector.collect(mode="daily-update")
    print(f"\n✓ Resultado:")
    print(f"  Status    : {result.status.name}")
    print(f"  Procesados: {result.records_collected}")


async def check_seasons():
    """Exibe estado das temporadas ativas antes e após."""
    from src.db.pool import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT l.code, s.is_current,
                   COUNT(m.match_id) AS total_matches,
                   COUNT(m.match_id) FILTER (WHERE m.status = 'finished') AS finished,
                   MAX(m.kickoff)::date AS last_kickoff
            FROM seasons s
            JOIN leagues l ON s.league_id = l.league_id
            LEFT JOIN matches m ON m.season_id = s.season_id
            WHERE s.is_current = TRUE
            GROUP BY l.code, s.is_current
            ORDER BY l.code
            """
        )
    print("\n=== Temporadas Ativas (is_current = TRUE) ===")
    for r in rows:
        pct = f"{r['finished']}/{r['total_matches']}" if r['total_matches'] else "0/0"
        print(f"  {r['code']:<12} | jogos: {pct:<10} | último: {r['last_kickoff']}")
    if not rows:
        print("  (nenhuma temporada ativa encontrada)")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", choices=["footystats", "football_data", "both"], default="both")
    args = parser.parse_args()

    print("\n--- Estado Inicial ---")
    await check_seasons()

    if args.job in ("footystats", "both"):
        print()
        await test_footystats()

    if args.job in ("football_data", "both"):
        print()
        await test_football_data()

    print("\n--- Estado Final ---")
    await check_seasons()


if __name__ == "__main__":
    asyncio.run(main())
