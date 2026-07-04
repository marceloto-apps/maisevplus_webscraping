import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

async def main():
    try:
        import asyncpg
    except ImportError:
        print("asyncpg não instalado. Rode 'pip install asyncpg' primeiro.")
        return

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        db_user = os.getenv("DB_USER", "maisevplus")
        db_pass = os.getenv("DB_PASS", "s32LSremnxBs")
        db_name = os.getenv("DB_NAME", "maisevplus_db")
        db_host = os.getenv("DB_HOST", "127.0.0.1")
        db_port = os.getenv("DB_PORT", "5432")
        dsn = f"postgres://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    else:
        dsn = database_url

    if "@localhost" in dsn:
        dsn = dsn.replace("@localhost", "@127.0.0.1")

    print("Conectando ao banco de dados...")
    conn = await asyncpg.connect(dsn=dsn)
    
    try:
        print("Conectado com sucesso. Iniciando transação para deduplicação...")
        async with conn.transaction():
            # 1. Identificar se a constraint já existe
            constraint_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_constraint 
                    WHERE conname = 'uq_odds_opening'
                )
            """)
            
            if constraint_exists:
                print("[LOG] A constraint uq_odds_opening já existe. Nada a fazer.")
                return

            # 2. Executar a query de exclusão de duplicatas em odds_history
            print("Removendo registros duplicados em odds_history (mantendo apenas uma linha por chave)...")
            
            # Deleta duplicados mantendo a linha com maior ctid
            delete_query = """
                DELETE FROM public.odds_history a
                USING public.odds_history b
                WHERE a.ctid < b.ctid
                  AND a.match_id = b.match_id
                  AND a.bookmaker_id = b.bookmaker_id
                  AND a.market_type = b.market_type
                  AND a.line IS NOT DISTINCT FROM b.line
                  AND a.period = b.period
                  AND a.is_opening = b.is_opening
                  AND a.time = b.time;
            """
            result = await conn.execute(delete_query)
            # result format is typically "DELETE count"
            print(f"[OK] Duplicados removidos: {result}")

            # 3. Tentar criar a constraint novamente
            print("Criando constraint uq_odds_opening...")
            await conn.execute("""
                ALTER TABLE public.odds_history
                ADD CONSTRAINT uq_odds_opening
                UNIQUE (match_id, bookmaker_id, market_type, line, period, is_opening, time)
            """)
            print("[OK] Constraint uq_odds_opening criada com sucesso!")
            
    except Exception as e:
        print(f"[ERRO] Falha ao deduplicar ou criar constraint: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
