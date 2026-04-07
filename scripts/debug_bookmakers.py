import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT bookmaker_id, name FROM bookmakers")
        print("--- Bookmakers in DB ---")
        for r in rows:
            print(f"ID={r['bookmaker_id']} Name='{r['name']}'")

if __name__ == "__main__":
    asyncio.run(main())
