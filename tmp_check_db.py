import asyncio
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("Sources in match_stats:")
        sources = await conn.fetch("SELECT source, count(*) FROM match_stats GROUP BY source")
        for s in sources:
            print(f" - {s['source']}: {s['count']}")
            
        print("\nSources in matches (where fbref_id is NOT NULL):")
        fbref_matches = await conn.fetchval("SELECT count(*) FROM matches WHERE fbref_id IS NOT NULL")
        print(f" - Matches with FBRef ID assigned: {fbref_matches}")

        print("\nSources in team_aliases:")
        alias_sources = await conn.fetch("SELECT source, count(*) FROM team_aliases GROUP BY source")
        for s in alias_sources:
            print(f" - {s['source']}: {s['count']}")
    await pool.close()

asyncio.run(main())
