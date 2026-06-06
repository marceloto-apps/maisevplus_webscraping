import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.collectors.flashscore.config import LEAGUE_FLASHSCORE_PATHS

async def main():
    load_dotenv()
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("=== SYNCHRONIZING FLASHSCORE PATHS IN DB ===")
        updated_count = 0
        for code, path in LEAGUE_FLASHSCORE_PATHS.items():
            # Check if league exists and has null or empty flashscore_path
            current_path = await conn.fetchval(
                "SELECT flashscore_path FROM leagues WHERE code = $1", code
            )
            if current_path is None or current_path == "":
                # Update it
                res = await conn.execute(
                    "UPDATE leagues SET flashscore_path = $1 WHERE code = $2",
                    path, code
                )
                if res.endswith(" 1"):
                    print(f"  [OK] Updated league {code} with path '{path}'")
                    updated_count += 1
            else:
                if current_path != path:
                    print(f"  ! League {code} has different path in DB ('{current_path}') vs Config ('{path}')")
                    
        print(f"\nTotal leagues updated: {updated_count}")
        
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
