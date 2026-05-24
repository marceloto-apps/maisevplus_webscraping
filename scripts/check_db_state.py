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
                
            print("\n=== FOREIGN KEYS ON TABLE 'matches' (via pg_constraint) ===")
            fkeys = await conn.fetch("""
                SELECT
                    conname AS constraint_name,
                    conrelid::regclass::text AS table_name,
                    confrelid::regclass::text AS foreign_table_name
                FROM pg_constraint
                WHERE conrelid = 'matches'::regclass AND contype = 'f'
            """)
            for fk in fkeys:
                print(f"  Constraint: {fk['constraint_name']} | Table: {fk['table_name']} -> References: {fk['foreign_table_name']}")
                
            print("\n=== ROW COUNT AND MAX ID PER SCHEMA ===")
            for table_name in ['leagues', 'matches', 'seasons', 'teams']:
                for schema in ['public', 'features']:
                    try:
                        table_exists = await conn.fetchval(f"""
                            SELECT EXISTS (
                                SELECT 1 FROM information_schema.tables 
                                WHERE table_schema = '{schema}' AND table_name = '{table_name}'
                            )
                        """)
                        if table_exists:
                            row_count = await conn.fetchval(f"SELECT COUNT(*) FROM {schema}.{table_name}")
                            max_id = None
                            if table_name == 'leagues':
                                max_id = await conn.fetchval(f"SELECT MAX(league_id) FROM {schema}.{table_name}")
                            elif table_name == 'seasons':
                                max_id = await conn.fetchval(f"SELECT MAX(season_id) FROM {schema}.{table_name}")
                            elif table_name == 'teams':
                                max_id = await conn.fetchval(f"SELECT MAX(team_id) FROM {schema}.{table_name}")
                            print(f"  {schema}.{table_name}: Rows: {row_count} | Max ID: {max_id}")
                    except Exception as err:
                        print(f"  Error reading {schema}.{table_name}: {err}")
                    
    except Exception as e:
        print("  DB Query/Connection Failed!")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
