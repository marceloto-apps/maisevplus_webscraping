import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        match_id = '999f4c8b-92e6-40ba-a678-441917b5910a'
        c = await conn.fetchval("SELECT count(*) FROM odds_history WHERE match_id = $1", match_id)
        fs_c = await conn.fetchval("SELECT count(*) FROM odds_history WHERE match_id = $1 AND source = 'flashscore'", match_id)
        
        print(f"Match {match_id}:")
        print(f"Total odds no DB: {c}")
        print(f"Total odds originadas do Flashscore: {fs_c}")
        
        if fs_c > 0:
            markets = await conn.fetch("SELECT market_type, count(*) FROM odds_history WHERE match_id = $1 AND source = 'flashscore' GROUP BY market_type", match_id)
            print("Mercados capturados do Flashscore:")
            for m in markets:
                print(f" - {m['market_type']}: {m['count']}")

if __name__ == "__main__":
    asyncio.run(main())
