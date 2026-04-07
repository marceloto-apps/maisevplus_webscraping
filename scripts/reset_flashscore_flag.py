import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.execute("UPDATE matches SET metadata = metadata - 'flashscore_scraped' WHERE flashscore_id IS NOT NULL")
        print(f"Marcadores removidos: {r}")

if __name__ == "__main__":
    asyncio.run(main())
