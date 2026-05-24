"""
scripts/diagnose_db.py
Diagnóstico da estrutura da tabela match_stats na VPS.
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

load_dotenv()

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("=== COLUNAS DA TABELA match_stats ===")
        rows = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'match_stats'
            ORDER BY ordinal_position;
        """)
        for r in rows:
            print(f"  {r['column_name']}: {r['data_type']}")
            
        print("\n=== EXISTÊNCIA DA VIEW v_match_full ===")
        view_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.views 
                WHERE table_name = 'v_match_full'
            );
        """)
        print(f"  v_match_full existe: {view_exists}")
        
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
