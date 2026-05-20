#!/usr/bin/env bash
# =============================================================
# Monitor — Acompanhar progresso da rodada complementar
# Uso: bash scripts/monitor_complementary.sh
# Rodar em outro terminal enquanto o scraper executa
# =============================================================

echo "=== Monitor: Fila Complementar ==="
echo "Atualiza a cada 30 segundos. Ctrl+C para sair."
echo ""

while true; do
    echo "--- $(date) ---"
    
    # Status da fila
    python -u -c "
import asyncio
from src.db.pool import get_pool

async def check():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT status, COUNT(*) as total 
            FROM fc_complementary_queue 
            GROUP BY status 
            ORDER BY total DESC
        ''')
        for r in rows:
            print(f'  {r[\"status\"]:12s} -> {r[\"total\"]}')
        
        pending = await conn.fetchval('''
            SELECT COUNT(*) FROM fc_complementary_queue WHERE status = 'pending'
        ''')
        completed = await conn.fetchval('''
            SELECT COUNT(*) FROM fc_complementary_queue WHERE status = 'completed'
        ''')
        print(f'  Progresso: {completed} concluídos | {pending} pendentes')
    await pool.close()

asyncio.run(check())
" 2>/dev/null
    
    echo ""
    sleep 30
done
