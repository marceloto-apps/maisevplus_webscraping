import os
import asyncio
from dotenv import load_dotenv
from src.db.pool import get_pool
from src.db import helpers

async def main():
    load_dotenv()
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("Lendo chaves do .env e populando a tabela api_keys...")
        

        # 2. Extrair API-Football (100 limit daily)
        af_keys = []
        for i in range(1, 6):
            val = os.getenv(f"API_FOOTBALL_KEY_{i}")
            if val:
                af_keys.append(val)
                

        # Inserir API Football
        for i, val in enumerate(af_keys):
            print(f"Inserindo API_FOOTBALL_KEY_{i+1}")
            await conn.execute("""
                INSERT INTO api_keys (service, key_label, key_value, limit_daily, limit_monthly, usage_today, usage_month, is_active)
                VALUES ('api_football', $1, $2, 100, NULL, 0, 0, TRUE)
            """, f"api_football_key_{i+1}", val)
            
        print(f"Sucesso! {len(af_keys)} API Football inseridas.")

if __name__ == '__main__':
    asyncio.run(main())
