import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

async def apply_migration():
    # As the user's psql is unavailable, we use the postgres driver directly.
    try:
        import asyncpg
    except ImportError:
        print("asyncpg não instalado. Rode 'pip install asyncpg' primeiro.")
        return

    db_user = os.getenv("DB_USER", "maisevplus")
    db_pass = os.getenv("DB_PASS", "s32LSremnxBs")
    db_name = os.getenv("DB_NAME", "maisevplus_db")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")

    print(f"Conectando ao banco de dados {db_name} em {db_host}...")
    try:
        conn = await asyncpg.connect(
            user=db_user,
            password=db_pass,
            database=db_name,
            host=db_host,
            port=db_port
        )
        print("Conectado com sucesso.")
        
        migration_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations", "017_prematch_odds.sql")
        
        if not os.path.exists(migration_path):
            print(f"Arquivo não encontrado: {migration_path}")
            return
            
        with open(migration_path, "r", encoding="utf-8") as f:
            sql = f.read()
            
        print("Executando arquivo de migração: 017_prematch_odds.sql")
        await conn.execute(sql)
        print("✅ Migração executada com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao executar migração: {e}")
    finally:
        if 'conn' in locals():
            await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_migration())
