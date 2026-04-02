import asyncio
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name IN ('odds', 'matches', 'fixtures', 'lineups', 'team_aliases') 
        ORDER BY table_name, ordinal_position;
        """)
        
        current_table = ""
        for r in rows:
            if r['table_name'] != current_table:
                current_table = r['table_name']
                print(f"\n--- Tabela: {current_table} ---")
            print(f" {r['column_name'].ljust(20)} | {r['data_type']}")

if __name__ == '__main__':
    asyncio.run(main())
