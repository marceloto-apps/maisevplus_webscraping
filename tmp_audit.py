import asyncio
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get match_stats columns
        cols = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'match_stats'
            ORDER BY ordinal_position
        """)
        print("=== match_stats table columns ===")
        for c in cols:
            print(f"  {c['column_name']:35s} {c['data_type']:20s} nullable={c['is_nullable']}")
        
        # Get matches columns too (for reference)
        cols2 = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'matches'
            ORDER BY ordinal_position
        """)
        print("\n=== matches table columns ===")
        for c in cols2:
            print(f"  {c['column_name']:35s} {c['data_type']}")
    await pool.close()

asyncio.run(main())
