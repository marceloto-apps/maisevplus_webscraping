"""
Script rápido para listar ligas e a quantidade de partidas pendentes de backfill.
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT l.code, l.name,
                   COUNT(m.match_id) as total_fs,
                   COUNT(m.match_id) FILTER (WHERE m.scraping_flashscore = true) as done,
                   COUNT(m.match_id) FILTER (WHERE m.scraping_flashscore IS NULL OR m.scraping_flashscore = false) as pending
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.status = 'finished' AND m.flashscore_id IS NOT NULL
            GROUP BY l.code, l.name
            HAVING COUNT(m.match_id) FILTER (WHERE m.scraping_flashscore IS NULL OR m.scraping_flashscore = false) > 0
            ORDER BY pending DESC
        """)
        
        print("\n" + "="*80)
        print(f"LIGAS COM PARTIDAS PENDENTES DE BACKFILL FLASHSCORE ({len(rows)} ligas):")
        print("="*80)
        for r in rows:
            print(f"  {r['code']:<12} | {r['name']:<30} | Total FS: {r['total_fs']:<5} | Coletadas: {r['done']:<5} | Pendentes: {r['pending']}")
        print("="*80 + "\n")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
