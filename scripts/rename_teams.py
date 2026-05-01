import asyncio, os
from dotenv import load_dotenv
load_dotenv()
async def rename_all_teams():
    import asyncpg
    dsn = os.getenv('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://')
    conn = await asyncpg.connect(dsn=dsn)
    
    res = await conn.execute("UPDATE teams SET name_canonical = '[LOST] Team ID ' || team_id::text")
    print(f'UPDATE RESULT: {res}')
    
    await conn.close()
asyncio.run(rename_all_teams())
