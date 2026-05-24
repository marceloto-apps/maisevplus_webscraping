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
                
            print("\n=== FOREIGN KEYS ON TABLE 'matches' ===")
            fkeys = await conn.fetch("""
                SELECT
                    tc.constraint_name, 
                    kcu.column_name, 
                    ccu.table_schema AS foreign_table_schema,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name 
                FROM 
                    information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name='matches'
            """)
            for fk in fkeys:
                print(f"  Constraint: {fk['constraint_name']} | Column: {fk['column_name']} -> References: {fk['foreign_table_schema']}.{fk['foreign_table_name']}({fk['foreign_column_name']})")
                
            print("\n=== SCHEMAS OF CORE TABLES ===")
            tables = await conn.fetch("""
                SELECT table_schema, table_name, table_type 
                FROM information_schema.tables 
                WHERE table_name IN ('leagues', 'matches', 'seasons', 'teams')
                ORDER BY table_name, table_schema
            """)
            for t in tables:
                print(f"  Schema: {t['table_schema']} | Table: {t['table_name']} | Type: {t['table_type']}")
                
            print("\n=== ROW COUNT AND MAX ID PER SCHEMA ===")
            for table_name in ['leagues', 'matches', 'seasons', 'teams']:
                for schema in ['public', 'maisevplus']:
                    try:
                        # Check if table exists in schema
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
