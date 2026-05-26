import sys
import os
import asyncio

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

async def audit():
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("=" * 60)
        print("  AUDITORIA DE TIMES E ALIASES")
        print("=" * 60)
        
        # 1. Total de times no banco
        total_teams = await conn.fetchval("SELECT COUNT(*) FROM teams")
        print(f"Total de times cadastrados no DB (teams): {total_teams}")
        
        # 2. Times com/sem alias do Flashscore
        teams_with_fs_alias = await conn.fetchval("""
            SELECT COUNT(DISTINCT team_id) 
            FROM team_aliases 
            WHERE source = 'flashscore'
        """)
        print(f"Times com pelo menos um alias 'flashscore': {teams_with_fs_alias}")
        print(f"Times sem nenhum alias 'flashscore': {total_teams - teams_with_fs_alias}")
        
        # Listar os times sem alias do flashscore (apenas os primeiros 15)
        if total_teams - teams_with_fs_alias > 0:
            missing_fs = await conn.fetch("""
                SELECT team_id, name_canonical, country 
                FROM teams t
                WHERE NOT EXISTS (
                    SELECT 1 FROM team_aliases ta 
                    WHERE ta.team_id = t.team_id AND ta.source = 'flashscore'
                )
                ORDER BY name_canonical
                LIMIT 15
            """)
            print("\n  Alguns times sem alias 'flashscore' (top 15):")
            for r in missing_fs:
                print(f"    - ID {r['team_id']}: {r['name_canonical']} ({r['country']})")
                
        # 3. Times com/sem alias do FootyStats
        teams_with_fts_alias = await conn.fetchval("""
            SELECT COUNT(DISTINCT team_id) 
            FROM team_aliases 
            WHERE source = 'footystats'
        """)
        print(f"\nTimes com pelo menos um alias 'footystats': {teams_with_fts_alias}")
        print(f"Times sem nenhum alias 'footystats': {total_teams - teams_with_fts_alias}")
        
        print("\n" + "=" * 60)
        print("  AUDITORIA DE REGISTRO DE PARTIDAS")
        print("=" * 60)
        
        # Total de partidas
        total_matches = await conn.fetchval("SELECT COUNT(*) FROM matches")
        print(f"Total de partidas registradas (matches): {total_matches}")
        
        # Partidas por status
        matches_by_status = await conn.fetch("""
            SELECT status, COUNT(*) 
            FROM matches 
            GROUP BY status 
            ORDER BY count DESC
        """)
        print("\nPartidas por status:")
        for r in matches_by_status:
            print(f"  - {r['status']}: {r['count']}")
            
        # Partidas da temporada atual sem flashscore_id
        missing_fs_id = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM matches m
            JOIN seasons s ON s.season_id = m.season_id
            WHERE s.is_current = TRUE 
              AND m.flashscore_id IS NULL
        """)
        print(f"\nPartidas da temporada atual sem flashscore_id: {missing_fs_id}")
        
        # Aliases desconhecidos pendentes de resolução
        pending_aliases = await conn.fetch("""
            SELECT source, COUNT(*) 
            FROM unknown_aliases 
            GROUP BY source
        """)
        if pending_aliases:
            print("\nAliases desconhecidos pendentes no unknown_aliases:")
            for r in pending_aliases:
                print(f"  - {r['source']}: {r['count']} nomes pendentes")
        else:
            print("\n✅ Nenhum alias desconhecido pendente de resolução!")
            
        # Partidas finalizadas sem odds coletadas do Flashscore
        finished_missing_odds = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM matches 
            WHERE status = 'finished' 
              AND flashscore_odds_collected = FALSE
        """)
        print(f"\nPartidas finalizadas (finished) sem odds coletadas (flashscore): {finished_missing_odds}")
        
        # Partidas finalizadas sem estatísticas coletadas do Flashscore
        finished_missing_stats = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM matches 
            WHERE status = 'finished' 
              AND flashscore_stats_collected = FALSE
        """)
        print(f"Partidas finalizadas (finished) sem estatísticas coletadas (flashscore): {finished_missing_stats}")
        print("=" * 60)

    await pool.close()

if __name__ == '__main__':
    asyncio.run(audit())
