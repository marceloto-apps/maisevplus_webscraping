import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

load_dotenv()

async def main():
    print("Conectando ao banco de dados...")
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        print("Iniciando transação para migração 024...")
        async with conn.transaction():
            # Alterar tipo da coluna collect_job_id para VARCHAR(100)
            print("Alterando tipo de collect_job_id na tabela odds_history para VARCHAR(100)...")
            await conn.execute("""
                ALTER TABLE public.odds_history 
                ALTER COLUMN collect_job_id TYPE VARCHAR(100);
            """)
            print("[OK] Coluna collect_job_id alterada com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
