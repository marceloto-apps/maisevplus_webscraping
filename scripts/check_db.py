import asyncio
import asyncpg
import os

async def main():
    pool = await asyncpg.create_pool("postgresql://admin:admin_password@127.0.0.1:5432/postgres")
    
    # 71 is the api-football league ID for BRA_SA, but maybe our db league_id is something else?
    print("Distinct league_id in matches for 2026:")
    rows = await pool.fetch("SELECT DISTINCT league_id, league FROM matches WHERE kickoff >= '2026-01-01'")
    for r in rows:
        print(f" - ID: {r['league_id']} | NAME: {r['league']}")

    c1 = await pool.fetchval("SELECT count(*) FROM matches WHERE league_id = 71 AND kickoff >= '2026-01-01'")
    print(f"Total BRA matches 2026 (71): {c1}")
    
    c2 = await pool.fetchval("SELECT count(*) FROM matches WHERE league_id = 71 AND kickoff >= '2026-01-01' AND status in ('FT', 'AET', 'PEN')")
    print(f"Total finished: {c2}")
    
    c3 = await pool.fetchval("SELECT count(*) FROM matches WHERE league_id = 71 AND kickoff >= '2026-01-01' AND status in ('FT', 'AET', 'PEN') AND flashscore_id IS NOT NULL")
    print(f"Total with FS_ID: {c3}")
    
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
