import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool, close_pool

MAPPING = {
    "Gremio": "Grêmio",
    "Remo": "Remo",
    "Mirassol": "Mirassol",
    "Bragantino": "%Bragantin%",
    "Bragantino2": "%Bragantin%",
    "Bahia": "Bahia",
    "Palmeiras": "Palmeiras",
    "Corinthians": "Corinthians",
    "Internacional": "Internacional",
    "Atletico-MG": "Atlético Mineiro",
    "Athletico-PR": "Athletico PR",
    "Flamengo RJ": "Flamengo",
    "Santos": "Santos",
    "Chapecoense-SC": "Chapecoense",
    "Vitoria": "Vitória",
    "Vasco": "Vasco%",
    "Botafogo RJ": "Botafogo",
    "Coritiba": "Coritiba",
    "Fluminense": "Fluminense",
    "Sao Paulo": "São Paulo",
    "Cruzeiro": "Cruzeiro"
}

async def main():
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        for fs_name, search_name in MAPPING.items():
            team_id = await conn.fetchval(
                "SELECT team_id FROM teams WHERE (name_canonical ILIKE $1 OR name_canonical = $2) AND team_id IN (SELECT home_team_id FROM matches JOIN leagues ON leagues.league_id = matches.league_id WHERE code = 'BRA_SA') LIMIT 1",
                search_name, fs_name
            )
            
            if team_id:
                await conn.execute("""
                    INSERT INTO team_aliases (team_id, source, alias_name)
                    VALUES ($1, 'flashscore', $2)
                    ON CONFLICT DO NOTHING
                """, team_id, fs_name)
                print(f"✅ Mapeado: {fs_name} para ID {team_id}")
            else:
                print(f"❌ Não encontrou na BRA_SA: {fs_name} (buscando por {search_name})")
                
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
