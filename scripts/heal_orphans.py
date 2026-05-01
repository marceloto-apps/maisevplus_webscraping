import asyncio, os
from dotenv import load_dotenv
load_dotenv()
async def heal_orphans():
    import asyncpg
    dsn = os.getenv('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://')
    conn = await asyncpg.connect(dsn=dsn)
    
    orphans_home = await conn.fetch('SELECT DISTINCT home_team_id FROM matches WHERE home_team_id NOT IN (SELECT team_id FROM teams)')
    orphans_away = await conn.fetch('SELECT DISTINCT away_team_id FROM matches WHERE away_team_id NOT IN (SELECT team_id FROM teams)')
    missing_ids = set([r['home_team_id'] for r in orphans_home] + [r['away_team_id'] for r in orphans_away])
    
    for tid in missing_ids:
        # Pega a primeira match dele pra ver se achamos pelo menos o país da liga
        eg_match = await conn.fetchrow('SELECT code, country FROM matches JOIN leagues ON leagues.league_id = matches.league_id WHERE home_team_id = $1 OR away_team_id = $1 LIMIT 1', tid)
        country = eg_match['country'] if eg_match else 'Unknown'
        await conn.execute("INSERT INTO teams (team_id, name_canonical, country) VALUES ($1, $2, $3)", tid, f'[LOST] Team ID {tid}', country)
        
    print(f'Criados {len(missing_ids)} stubs para não quebrar a Foreign Key dos jogos.')
    if missing_ids:
        await conn.execute("SELECT setval('teams_team_id_seq', (SELECT MAX(team_id) FROM teams))")
    await conn.close()
asyncio.run(heal_orphans())
