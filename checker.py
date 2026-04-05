import asyncio, sys
sys.path.insert(0,'.')
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        schema = await conn.fetch('''
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'match_stats'
        ''')
        for col in schema:
            print(f"{col['column_name']}: {col['data_type']}")
        
        # Checking data for the match specifically
        match_id = 'f6d15ade-b1f9-4536-9f3b-f6d82aaa5bc9'
        rows = await conn.fetch('''
            SELECT * FROM match_stats WHERE match_id = $1
        ''', match_id)
        if rows:
            print(f"\nFound {len(rows)} records in match_stats for this match:")
            for k, v in dict(rows[0]).items():
                print(f"  {k}: {v}")
        else:
            print("\nNo records found in match_stats for this match.")

asyncio.run(main())
