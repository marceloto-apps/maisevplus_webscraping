import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

async def apply_migration():
    try:
        import asyncpg
    except ImportError:
        print("asyncpg nao instalado. Rode 'pip install asyncpg' primeiro.")
        return

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Fallback to individual env vars
        db_user = os.getenv("DB_USER", "maisevplus")
        db_pass = os.getenv("DB_PASS", "s32LSremnxBs")
        db_name = os.getenv("DB_NAME", "maisevplus_db")
        db_host = os.getenv("DB_HOST", "127.0.0.1")
        db_port = os.getenv("DB_PORT", "5432")
        dsn = f"postgres://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    else:
        dsn = database_url

    # Replace local/ipv6 issues if localhost is used
    if "@localhost" in dsn:
        dsn = dsn.replace("@localhost", "@127.0.0.1")

    print("Conectando ao banco de dados...")
    try:
        conn = await asyncpg.connect(dsn=dsn)
        print("Conectado com sucesso.")
        
        migration_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations", "022_opening_odds_health.sql")
        
        if not os.path.exists(migration_path):
            print(f"Arquivo nao encontrado: {migration_path}")
            return
            
        with open(migration_path, "r", encoding="utf-8") as f:
            sql = f.read()
            
        print("Executando arquivo de migracao: 022_opening_odds_health.sql")
        await conn.execute(sql)
        print("[OK] Migracao executada com sucesso!")
        
    except Exception as e:
        print(f"[ERROR] Erro ao executar migracao: {e}")
    finally:
        if 'conn' in locals():
            await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_migration())
