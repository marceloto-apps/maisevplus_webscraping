import asyncio
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        fc_ed_id = await conn.fetchval("SELECT team_id FROM teams WHERE name_canonical = 'FC Edinburgh'")
        ed_city_id = await conn.fetchval("SELECT team_id FROM teams WHERE name_canonical = 'Edinburgh City'")
        
        print(f"FC Edinburgh ID: {fc_ed_id}, Edinburgh City ID: {ed_city_id}")
        
        if fc_ed_id and ed_city_id:
            # 1. Update the alias to point to FC Edinburgh (overwrite previous if exists)
            await conn.execute("""
                UPDATE team_aliases 
                SET team_id = $1 
                WHERE source = 'footystats' AND alias_name = 'edinburgh city'
            """, fc_ed_id)
            
            # Insert if it wasn't there before mapping to Edinburgh City
            await conn.execute("""
                INSERT INTO team_aliases (source, alias_name, team_id) 
                VALUES ('footystats', 'edinburgh city', $1) 
                ON CONFLICT (source, alias_name) DO UPDATE SET team_id = EXCLUDED.team_id
            """, fc_ed_id)
            print("✅ Alias 'edinburgh city' forcado para apontar para FC Edinburgh.")
            
            # 2. Delete ALL ghost matches that were created tying to Edinburgh City ID directly
            ghosts = await conn.fetch("""
                SELECT match_id FROM matches 
                WHERE footystats_id IS NOT NULL 
                AND (home_team_id = $1 OR away_team_id = $1)
            """, ed_city_id)
            
            if ghosts:
                ghost_ids = [g['match_id'] for g in ghosts]
                await conn.execute("DELETE FROM match_stats WHERE match_id = ANY($1)", ghost_ids)
                await conn.execute("DELETE FROM matches WHERE match_id = ANY($1)", ghost_ids)
                print(f"✅ Deletados {len(ghost_ids)} matches fantasmas associados ao antigo ID do Edinburgh City.")
            else:
                print("Nenhum ghost match associado ao antigo ID.")

    await pool.close()

asyncio.run(main())
