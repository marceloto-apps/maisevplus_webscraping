import asyncio
from dotenv import load_dotenv
from src.db.pool import get_pool

async def main():
    load_dotenv()
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("Resetando limites diarios das chaves do api_football...")
        await conn.execute("""
            UPDATE api_keys 
            SET usage_today = 0 
            WHERE service = 'api_football' AND is_active = TRUE;
        """)
        print("Sucesso! Limites diarios zerados.")

if __name__ == '__main__':
    asyncio.run(main())
