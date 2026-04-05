"""
Ajuste de API keys: KEY_1 → VIP (7500/dia), Keys 2-7 → desativadas.
Uso no VPS: .venv/bin/python scripts/update_api_keys.py
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Estado atual
        rows = await conn.fetch("""
            SELECT key_id, key_label, limit_daily, usage_today, is_active
            FROM api_keys WHERE service = 'api_football' ORDER BY key_id
        """)
        
        print("=== ESTADO ATUAL ===")
        for r in rows:
            status = "🟢" if r['is_active'] else "🔴"
            print(f"  {status} key_id={r['key_id']}  label={r['key_label']}  limit={r['limit_daily']}  usage={r['usage_today']}")
        
        if not rows:
            print("Nenhuma key api_football encontrada!")
            return
        
        key1_id = rows[0]['key_id']
        
        # 2. KEY_1 → VIP 7500/dia
        await conn.execute(
            "UPDATE api_keys SET limit_daily = 7500, is_active = TRUE WHERE key_id = $1",
            key1_id
        )
        
        # 3. Desativar todas as outras
        await conn.execute("""
            UPDATE api_keys SET is_active = FALSE
            WHERE service = 'api_football' AND key_id != $1
        """, key1_id)
        
        # 4. Resultado final
        rows2 = await conn.fetch("""
            SELECT key_id, key_label, limit_daily, usage_today, is_active
            FROM api_keys WHERE service = 'api_football' ORDER BY key_id
        """)
        
        print("\n=== ESTADO FINAL ===")
        for r in rows2:
            status = "🟢 ATIVA" if r['is_active'] else "🔴 INATIVA"
            print(f"  {status}  key_id={r['key_id']}  label={r['key_label']}  limit={r['limit_daily']}  usage={r['usage_today']}")

if __name__ == '__main__':
    asyncio.run(main())
