"""Fix VPS: Encontrar pares duplicados (football-data vs footystats) e mesclar"""
import asyncio
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Encontrar pares: match do football-data (sem stats) + match do footystats (com stats)
        # Mesmo league_id, mesmos times, data +-1 dia
        pairs = await conn.fetch("""
            SELECT 
                o.match_id AS fd_match_id,
                f.match_id AS fs_match_id,
                f.footystats_id,
                o.kickoff AS fd_kickoff,
                f.kickoff AS fs_kickoff
            FROM matches o
            JOIN matches f ON o.league_id = f.league_id
                          AND o.home_team_id = f.home_team_id
                          AND o.away_team_id = f.away_team_id
                          AND ABS(o.kickoff::date - f.kickoff::date) <= 1
                          AND o.match_id != f.match_id
            WHERE o.footystats_id IS NULL
              AND f.footystats_id IS NOT NULL
              AND o.status = 'finished'
              AND NOT EXISTS (SELECT 1 FROM match_stats ms WHERE ms.match_id = o.match_id AND ms.source = 'footystats')
              AND EXISTS (SELECT 1 FROM match_stats ms WHERE ms.match_id = f.match_id AND ms.source = 'footystats')
        """)
        
        print(f"Pares duplicados encontrados: {len(pairs)}")
        
        merged = 0
        for p in pairs:
            fd_id = p['fd_match_id']   # match original (football-data) — manter
            fs_id = p['fs_match_id']   # match duplicado (footystats) — deletar
            
            # 1. Mover stats do duplicado para o original
            moved = await conn.execute("""
                UPDATE match_stats SET match_id = $1 WHERE match_id = $2
            """, fd_id, fs_id)
            
            # 2. Copiar footystats_id e HT scores para o original
            await conn.execute("""
                UPDATE matches SET 
                    footystats_id = $1,
                    ht_home = COALESCE(ht_home, (SELECT ht_home FROM matches WHERE match_id = $3)),
                    ht_away = COALESCE(ht_away, (SELECT ht_away FROM matches WHERE match_id = $3)),
                    updated_at = NOW()
                WHERE match_id = $2
            """, p['footystats_id'], fd_id, fs_id)
            
            # 3. Deletar match duplicado
            await conn.execute("DELETE FROM matches WHERE match_id = $1", fs_id)
            merged += 1
        
        # Resultado
        remaining = await conn.fetchval("""
            SELECT COUNT(*) FROM matches m
            WHERE m.status = 'finished'
            AND NOT EXISTS (SELECT 1 FROM match_stats ms WHERE ms.match_id = m.match_id AND ms.source = 'footystats')
        """)
        total = await conn.fetchval("SELECT COUNT(*) FROM matches")
        stats = await conn.fetchval("SELECT COUNT(*) FROM match_stats WHERE source = 'footystats'")
        
        print(f"\n✅ Mesclados: {merged}")
        print(f"matches total: {total:,}")
        print(f"match_stats: {stats:,}")
        print(f"Gap restante: {remaining}")

    await pool.close()

asyncio.run(main())
