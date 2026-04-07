import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        league_id = await conn.fetchval("SELECT league_id FROM leagues WHERE code = 'BRA_SA'")
        print(f"BRA_SA League ID na base de dados (leagues): {league_id}")
        
        count = await conn.fetchval("SELECT count(*) FROM matches WHERE league_id = $1 AND kickoff >= '2026-01-01'", league_id)
        print(f"Partidas de 2026 para essa liga (matches): {count}")
        
        statuses = await conn.fetch("SELECT status, count(*) FROM matches WHERE league_id = $1 AND kickoff >= '2026-01-01' GROUP BY status", league_id)
        for s in statuses:
            print(f"  Status '{s['status']}': {s['count']} partidas")

if __name__ == "__main__":
    asyncio.run(main())
