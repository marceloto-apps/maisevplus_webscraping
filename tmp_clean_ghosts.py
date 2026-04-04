"""Fix: Limpar ghost matches criados com IDs de times errados (ex: Carlisle ao invés de Newcastle)"""
import asyncio
from src.db.pool import get_pool
from src.collectors.footystats.api_client import FootyStatsClient
from src.normalizer.team_resolver import TeamResolver
from src.collectors.footystats.matches_collector import parse_kickoff

async def main():
    pool = await get_pool()
    client = FootyStatsClient()
    await TeamResolver.load_cache()
    
    async with pool.acquire() as conn:
        print("Buscando ligas com gap...")
        seasons = await conn.fetch("""
            SELECT s.footystats_season_id, s.league_id, l.code
            FROM seasons s JOIN leagues l ON l.league_id = s.league_id
            WHERE s.footystats_season_id IS NOT NULL
              AND l.code IN ('ENG_PL', 'SCO_L1', 'NED_ED', 'TUR_SL')
        """)
        
        fixed_count = 0
        deleted_count = 0
        
        for s in seasons:
            data = await client.fetch_season_matches(s['footystats_season_id'])
            if not data: continue
            
            for raw in data:
                fs_id = raw.get('id')
                home_name = str(raw.get('home_name', ''))
                away_name = str(raw.get('away_name', ''))
                kickoff = parse_kickoff(raw.get('date_unix'))
                
                # O ID correto HOJE (agora que os aliases foram corrigidos)
                correct_home_id = await TeamResolver.resolve("footystats", home_name)
                correct_away_id = await TeamResolver.resolve("footystats", away_name)
                
                if not correct_home_id or not correct_away_id:
                    continue
                
                # Procurar se há um match salvo com esse fs_id e times incorretos
                ghost = await conn.fetchrow("""
                    SELECT match_id, home_team_id, away_team_id
                    FROM matches 
                    WHERE footystats_id = $1 
                      AND (home_team_id != $2 OR away_team_id != $3)
                """, fs_id, correct_home_id, correct_away_id)
                
                if ghost:
                    ghost_id = ghost['match_id']
                    
                    # 1. Tentar encontrar o match ORIGINAL 'órfão' para estes times/data
                    real = await conn.fetchrow("""
                        SELECT match_id FROM matches
                        WHERE league_id = $1 AND home_team_id = $2 AND away_team_id = $3
                        AND ABS(kickoff::date - $4::date) <= 1
                        AND footystats_id IS NULL
                    """, s['league_id'], correct_home_id, correct_away_id, kickoff.date())
                    
                    if real:
                        real_id = real['match_id']
                        # Mover as estáticas e footystats_id para o real_id
                        await conn.execute("UPDATE match_stats SET match_id = $1 WHERE match_id = $2", real_id, ghost_id)
                        await conn.execute("UPDATE matches SET footystats_id = $1, updated_at = NOW() WHERE match_id = $2", fs_id, real_id)
                        fixed_count += 1
                        
                        # Deletar o fantasma que tem os times errados
                        await conn.execute("DELETE FROM match_stats WHERE match_id = $1", ghost_id)
                        await conn.execute("DELETE FROM matches WHERE match_id = $1", ghost_id)
                    else:
                        # Se não encontrar um original, mas o fantasma está errado, apaga ele 
                        # para o backfill poder criar/processar corretamente depois
                        await conn.execute("DELETE FROM match_stats WHERE match_id = $1", ghost_id)
                        await conn.execute("DELETE FROM matches WHERE match_id = $1", ghost_id)
                        deleted_count += 1
        
        print(f"✅ Feito!")
        print(f"Stats vinculadas a matches originais corrigidas: {fixed_count}")
        print(f"Matches fantasmas deletados completamente: {deleted_count}")
        
        remaining = await conn.fetchval("""
            SELECT COUNT(*) FROM matches m
            WHERE m.status = 'finished'
            AND NOT EXISTS (SELECT 1 FROM match_stats ms WHERE ms.match_id = m.match_id AND ms.source = 'footystats')
            AND m.league_id IN (SELECT league_id FROM leagues WHERE code IN ('ENG_PL', 'SCO_L1', 'NED_ED', 'TUR_SL'))
        """)
        print(f"Gap atual nestas 4 ligas: {remaining}")

    await client.close()
    await pool.close()

asyncio.run(main())
