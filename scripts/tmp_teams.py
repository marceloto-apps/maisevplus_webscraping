import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool, close_pool

async def run():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT t.team_id, t.name_canonical FROM teams t JOIN matches m ON t.team_id = m.home_team_id JOIN leagues l ON l.league_id = m.league_id WHERE l.code = 'BRA_SA' GROUP BY t.team_id, t.name_canonical")
        for r in rows:
            print(f"{r['team_id']}: {r['name_canonical']}")
    await close_pool()

asyncio.run(run())
