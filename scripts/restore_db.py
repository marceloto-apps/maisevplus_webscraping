import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

async def restore():
    import asyncpg
    dsn = os.getenv('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://')
    conn = await asyncpg.connect(dsn=dsn)
    
    with open('migrations/full_schema.sql.bak', 'r', encoding='utf-8') as f:
        content = f.read()
        
    statements = [s.strip() for s in content.split(';') if s.strip()]
    inserted = 0
    for stmt in statements:
        # Pega a primeira palavra para checar clean
        clean_stmt = ' '.join(stmt.split())
        if clean_stmt.startswith('INSERT INTO leagues') or \
           clean_stmt.startswith('INSERT INTO public.leagues') or \
           clean_stmt.startswith('INSERT INTO seasons') or \
           clean_stmt.startswith('INSERT INTO public.seasons') or \
           clean_stmt.startswith('INSERT INTO bookmakers') or \
           clean_stmt.startswith('INSERT INTO public.bookmakers'):
            # try to execute
            try:
                await conn.execute(stmt)
                inserted += 1
            except Exception as e:
                print(f"Skipping insert (maybe already there or invalid): {e}")

    # Now we need to rebuild teams!    
    print(f"Master inserts executados: {inserted}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(restore())
