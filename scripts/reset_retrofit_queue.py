"""Script para resetar o status de no_opening das partidas no retrofit_match_log
e resetar contadores e ligas pendentes na retrofit_queue.
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool
from src.db.logger import configure_logging, get_logger

load_dotenv()
configure_logging()
logger = get_logger("reset_retrofit_queue")

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("=== RESET DA FILA E LOGS DE RETROFIT ===")
        
        # 1. Contar no_opening atuais
        no_opening_count = await conn.fetchval("SELECT COUNT(*) FROM retrofit_match_log WHERE status = 'no_opening'")
        print(f"Total de registros 'no_opening' atualmente: {no_opening_count}")
        
        # 2. Deletar registros 'no_opening' do retrofit_match_log
        deleted = await conn.execute("DELETE FROM retrofit_match_log WHERE status = 'no_opening'")
        print(f"[OK] Removidos registros com status 'no_opening': {deleted}")
        
        # 3. Resetar contadores das ligas que não estão concluídas ou resetar todas as ligas pending/failed
        updated_q = await conn.execute("""
            UPDATE retrofit_queue
            SET processed_matches = 0,
                success_matches = 0,
                attempts = 0,
                status = 'pending'
            WHERE status != 'completed'
        """)
        print(f"[OK] Ligas resetadas para 'pending' na retrofit_queue: {updated_q}")
        
        # 4. Exibir sumário atualizado da fila
        rows = await conn.fetch("SELECT status, COUNT(*) as cnt FROM retrofit_queue GROUP BY status ORDER BY status")
        print("\nStatus atual da retrofit_queue:")
        for r in rows:
            print(f"  {r['status']}: {r['cnt']}")

if __name__ == "__main__":
    asyncio.run(main())
