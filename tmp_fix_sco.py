import asyncio
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Encontrar o ID do "FC Edinburgh"
        team_id = await conn.fetchval(
            "SELECT team_id FROM teams WHERE name_canonical = 'FC Edinburgh'"
        )
        if team_id:
            await conn.execute("""
                INSERT INTO team_aliases (source, alias_name, team_id) 
                VALUES ('footystats', 'edinburgh city', $1) 
                ON CONFLICT DO NOTHING
            """, team_id)
            print("✅ Alias 'edinburgh city' -> 'FC Edinburgh' criado com sucesso.")
        else:
            print("❌ Time 'FC Edinburgh' não encontrado.")

    await pool.close()

asyncio.run(main())
