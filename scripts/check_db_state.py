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
                
            print("\n=== ALL DATABASE CONSTRAINTS POINTING TO 'features' SCHEMA ===")
            fkeys_to_features = await conn.fetch("""
                SELECT
                    tc.table_schema,
                    tc.table_name,
                    tc.constraint_name,
                    ccu.table_schema AS foreign_table_schema,
                    ccu.table_name AS foreign_table_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.constraint_column_usage AS ccu 
                  ON tc.constraint_name = ccu.constraint_name
                  AND tc.table_schema = ccu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' AND ccu.table_schema = 'features'
            """)
            for fk in fkeys_to_features:
                print(f"  Table: {fk['table_schema']}.{fk['table_name']} | Constraint: {fk['constraint_name']} -> References: {fk['foreign_table_schema']}.{fk['foreign_table_name']}")
                
    except Exception as e:
        print("  DB Query/Connection Failed!")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
