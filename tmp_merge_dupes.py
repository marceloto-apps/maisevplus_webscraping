"""Fix: encontrar matches 'fantasma' criados pelo backfill e mesclar com os originais"""
import asyncio
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Matches fantasma: têm footystats_id MAS o match real (composite) é diferente
        # Encontrar: para cada match com footystats_id, verificar se existe outro match
        # com mesmos times + data que NÃO tem footystats_id
        ghosts = await conn.fetch("""
            SELECT f.match_id AS ghost_id, f.footystats_id, f.kickoff AS ghost_kickoff,
                   o.match_id AS real_id, o.kickoff AS real_kickoff,
                   f.league_id,
                   f.home_team_id, f.away_team_id
            FROM matches f
            JOIN matches o ON o.league_id = f.league_id
                          AND o.home_team_id = f.home_team_id
                          AND o.away_team_id = f.away_team_id
                          AND ABS(o.kickoff::date - f.kickoff::date) <= 1
                          AND o.match_id != f.match_id
            WHERE f.footystats_id IS NOT NULL
              AND o.footystats_id IS NULL
              AND o.status = 'finished'
        """)
        
        print(f"Matches fantasma encontrados: {len(ghosts)}")
        
        merged = 0
        for g in ghosts:
            ghost_id = g['ghost_id']
            real_id = g['real_id']
            
            # 1. Mover stats do fantasma para o real
            await conn.execute(
                "UPDATE match_stats SET match_id = $1 WHERE match_id = $2",
                real_id, ghost_id
            )
            
            # 2. Copiar footystats_id e HT para o real
            await conn.execute("""
                UPDATE matches SET 
                    footystats_id = $1,
                    ht_home = COALESCE(ht_home, (SELECT ht_home FROM matches WHERE match_id = $3)),
                    ht_away = COALESCE(ht_away, (SELECT ht_away FROM matches WHERE match_id = $3)),
                    updated_at = NOW()
                WHERE match_id = $2
            """, g['footystats_id'], real_id, ghost_id)
            
            # 3. Deletar fantasma
            await conn.execute("DELETE FROM match_stats WHERE match_id = $1", ghost_id)
            await conn.execute("DELETE FROM matches WHERE match_id = $1", ghost_id)
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
