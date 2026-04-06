"""
scripts/check_flashscore_ids.py
Verifica quantos matches já têm flashscore_id no banco.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool


async def run():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Total de matches
        total = await conn.fetchval("SELECT COUNT(*) FROM matches")
        with_fs = await conn.fetchval("SELECT COUNT(*) FROM matches WHERE flashscore_id IS NOT NULL")
        without_fs = total - with_fs

        print(f"=== FLASHSCORE IDs STATUS ===\n")
        print(f"  Total matches:         {total}")
        print(f"  Com flashscore_id:     {with_fs}")
        print(f"  Sem flashscore_id:     {without_fs}")
        print(f"  Cobertura:             {with_fs/total*100:.1f}%" if total else "  Cobertura: N/A")

        # 2. Breakdown por liga
        print(f"\n=== POR LIGA ===\n")
        rows = await conn.fetch("""
            SELECT l.code, 
                   COUNT(*) AS total,
                   COUNT(m.flashscore_id) AS com_id,
                   COUNT(*) - COUNT(m.flashscore_id) AS sem_id
            FROM matches m
            JOIN leagues l ON l.league_id = m.league_id
            GROUP BY l.code
            ORDER BY l.code
        """)
        print(f"  {'Liga':<10} {'Total':>7} {'Com ID':>8} {'Sem ID':>8} {'%':>7}")
        print(f"  {'-'*10} {'-'*7} {'-'*8} {'-'*8} {'-'*7}")
        for r in rows:
            pct = (r['com_id'] / r['total'] * 100) if r['total'] > 0 else 0
            print(f"  {r['code']:<10} {r['total']:>7} {r['com_id']:>8} {r['sem_id']:>8} {pct:>6.1f}%")

        # 3. Bookmakers no DB
        print(f"\n=== BOOKMAKERS CADASTRADOS ===\n")
        bms = await conn.fetch("SELECT bookmaker_id, name, display_name, type FROM bookmakers ORDER BY bookmaker_id")
        for b in bms:
            print(f"  {b['bookmaker_id']:3d} | {b['name']:<15s} | {b['display_name']:<20s} | {b['type']}")


if __name__ == "__main__":
    asyncio.run(run())
