"""Auditoria final: matches vs match_stats + qualidade completa"""
import asyncio
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("=" * 70)
        print("AUDITORIA FINAL ABSOLUTA — FOOTYSTATS DATA PIPELINE")
        print("=" * 70)

        # 1. Volumetria
        matches_total = await conn.fetchval("SELECT COUNT(*) FROM matches")
        matches_finished = await conn.fetchval("SELECT COUNT(*) FROM matches WHERE status = 'finished'")
        stats_total = await conn.fetchval("SELECT COUNT(*) FROM match_stats WHERE source = 'footystats'")
        
        print(f"\n📊 VOLUMETRIA:")
        print(f"  matches (total):          {matches_total:,}")
        print(f"  matches (finished):       {matches_finished:,}")
        print(f"  match_stats (footystats): {stats_total:,}")
        print(f"  Cobertura Global: {(stats_total/max(matches_finished,1))*100:.2f}%")

        orphans = await conn.fetchval("""
            SELECT COUNT(*) FROM matches m 
            WHERE m.status = 'finished' 
            AND NOT EXISTS (SELECT 1 FROM match_stats ms WHERE ms.match_id = m.match_id AND ms.source = 'footystats')
        """)
        print(f"  Gap restante: {orphans:,} matches (Matches sem dados no fornecedor)")

        # 2. Cobertura por liga
        print(f"\n📋 COBERTURA POR LIGA (O QUADRO DE HONRA):")
        rows = await conn.fetch("""
            SELECT l.code, l.name,
                   COUNT(DISTINCT m.match_id) AS total_matches,
                   COUNT(DISTINCT ms.match_id) AS with_stats,
                   COUNT(DISTINCT m.match_id) - COUNT(DISTINCT ms.match_id) AS missing
            FROM matches m
            JOIN leagues l ON l.league_id = m.league_id
            LEFT JOIN match_stats ms ON ms.match_id = m.match_id AND ms.source = 'footystats'
            WHERE m.status = 'finished'
            GROUP BY l.code, l.name
            ORDER BY (COUNT(DISTINCT m.match_id) - COUNT(DISTINCT ms.match_id)) ASC, l.code ASC
        """)
        print(f"  {'Liga':<12} {'Nome':<30} {'Total':>7} {'Stats':>7} {'Falta':>7} {'%':>6}")
        print(f"  {'─'*12} {'─'*30} {'─'*7} {'─'*7} {'─'*7} {'─'*6}")
        for r in rows:
            pct = r['with_stats']/max(r['total_matches'],1)*100
            flag = " ✅" if r['missing'] == 0 else ""
            print(f"  {r['code']:<12} {r['name'][:30]:<30} {r['total_matches']:>7,} {r['with_stats']:>7,} {r['missing']:>7,} {pct:>5.1f}%{flag}")

    await pool.close()

asyncio.run(main())
