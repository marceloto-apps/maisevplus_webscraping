import asyncio
import os
import sys
import yaml
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

async def sync_leagues():
    import asyncpg
    dsn = os.getenv('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://')
    conn = await asyncpg.connect(dsn=dsn)
    
    config_path = os.path.join('src', 'config', 'leagues.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        leagues_data = yaml.safe_load(f)

    updated = 0
    for code, info in leagues_data.get('leagues', {}).items():
        af_id = info.get('api_football_league_id')
        if af_id is not None:
            await conn.execute(
                "UPDATE leagues SET api_football_league_id = $1 WHERE code = $2",
                af_id, code
            )
            updated += 1
            print(f"Atualizado {code} com api_football_league_id = {af_id}")

    print(f"Total atualizado: {updated}")
    await conn.close()

if __name__ == '__main__':
    asyncio.run(sync_leagues())
