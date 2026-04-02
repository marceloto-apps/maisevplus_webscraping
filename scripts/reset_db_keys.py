import asyncio
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("Resetando quotas bloqueadas no DB...")
        await conn.execute("UPDATE api_keys SET usage_today = 0, usage_month = 0, last_reset_at = NOW();")
        
        rows = await conn.fetch("SELECT key_id, service, key_label, usage_today, usage_month FROM api_keys")
        for r in rows:
            print(dict(r))

if __name__ == '__main__':
    asyncio.run(main())
