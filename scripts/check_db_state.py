import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

async def main():
    load_dotenv()
    print("=== ENVIRONMENT DATABASE VARIABLES ===")
    for key in ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DATABASE_URL"]:
        val = os.getenv(key)
        if val:
            if "postgresql://" in val or "postgres://" in val:
                # Mask password
                parts = val.split("@")
                if len(parts) > 1:
                    print(f"  {key}: ...@{parts[-1]}")
                else:
                    print(f"  {key}: {val}")
            else:
                print(f"  {key}: {val}")
        else:
            print(f"  {key}: NOT SET")

    print("\n=== TESTING CONNECTION ===")
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1")
            print("  DB Connection Success! SELECT 1 returned:", val)
            
            print("\n=== LEAGUES ===")
            leagues = await conn.fetch("SELECT league_id, code, name, is_active, primary_source FROM leagues ORDER BY league_id")
            for l in leagues:
                print(f"  ID: {l['league_id']} | Code: {l['code']} | Name: {l['name']} | Active: {l['is_active']} | Primary Source: {l['primary_source']}")
                
            print("\n=== SEASONS FOR ARG_LP (league_id=28) ===")
            seasons = await conn.fetch("SELECT season_id, league_id, label, is_current FROM seasons WHERE league_id = 28")
            for s in seasons:
                print(f"  ID: {s['season_id']} | League ID: {s['league_id']} | Label: {s['label']} | Current: {s['is_current']}")
                
    except Exception as e:
        print("  DB Query/Connection Failed!")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
