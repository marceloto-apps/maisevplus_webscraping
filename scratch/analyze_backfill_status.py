import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

async def main():
    load_dotenv()
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("=== COMPACT SUMMARY ===", flush=True)
        
        # 1. Total pending matches for all active leagues
        pending_total = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            WHERE l.is_active = TRUE
              AND m.status = 'finished'
              AND m.flashscore_id IS NOT NULL
              AND (m.scraping_flashscore IS NULL OR m.scraping_flashscore = FALSE)
              AND (m.flashscore_stats_collected = FALSE OR m.flashscore_odds_collected = FALSE)
        """)
        print(f"Total Flashscore pending matches: {pending_total}", flush=True)
        
        # 2. Unresolved aliases
        unresolved_aliases = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM unknown_aliases 
            WHERE source = 'flashscore' AND resolved = FALSE
        """)
        print(f"Total Unresolved Flashscore Aliases: {unresolved_aliases}", flush=True)

        print("\n=== BREAKDOWN OF PENDING MATCHES BY LEAGUE AND SEASON ===", flush=True)
        breakdown = await conn.fetch("""
            SELECT l.code as league_code, s.label as season, COUNT(*) as pending_count
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            JOIN seasons s ON m.season_id = s.season_id
            WHERE l.is_active = TRUE
              AND m.status = 'finished'
              AND m.flashscore_id IS NOT NULL
              AND (m.scraping_flashscore IS NULL OR m.scraping_flashscore = FALSE)
              AND (m.flashscore_stats_collected = FALSE OR m.flashscore_odds_collected = FALSE)
            GROUP BY l.code, s.label
            ORDER BY l.code, s.label
        """)
        for b in breakdown:
            print(f"  {b['league_code']} ({b['season']}): {b['pending_count']} matches pending", flush=True)

        print("\n=== UNRESOLVED ALIASES SAMPLE ===", flush=True)
        aliases = await conn.fetch("""
            SELECT league_code, raw_name, first_seen 
            FROM unknown_aliases 
            WHERE source = 'flashscore' AND resolved = FALSE
            ORDER BY first_seen DESC
            LIMIT 10
        """)
        for a in aliases:
            print(f"  League: {a['league_code']} | Team: {a['raw_name']} | First seen: {a['first_seen']}", flush=True)

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
