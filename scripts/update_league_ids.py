import asyncio
import os, sys
import yaml
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    yaml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "config", "leagues.yaml")
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        
    async with pool.acquire() as conn:
        for l_code, l_info in config.get("leagues", {}).items():
            api_id = l_info.get("api_football_league_id")
            if api_id is not None:
                await conn.execute("UPDATE leagues SET api_football_league_id = $1 WHERE code = $2", api_id, l_code)
                print(f"Atualizado {l_code} -> API ID {api_id}")
                
if __name__ == '__main__':
    asyncio.run(main())
