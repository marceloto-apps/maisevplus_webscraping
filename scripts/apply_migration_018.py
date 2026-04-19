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
        print("asyncpg não instalado. Rode 'pip install asyncpg' primeiro.")
        return

    db_user = os.getenv("DB_USER", "maisevplus")
    db_pass = os.getenv("DB_PASS", "s32LSremnxBs")
    db_name = os.getenv("DB_NAME", "maisevplus_db")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")

    url = os.getenv("DATABASE_URL")
    if url:
        dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    else:
        dsn = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    print(f"Conectando ao banco de dados...")
    try:
        conn = await asyncpg.connect(dsn=dsn)
        print("Conectado com sucesso.")
        
        migration_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations", "018_data_quality_flags.sql")
        
        if not os.path.exists(migration_path):
            print(f"Arquivo não encontrado: {migration_path}")
            return
            
        with open(migration_path, "r", encoding="utf-8") as f:
            sql = f.read()
            
        print("Executando arquivo de migração: 018_data_quality_flags.sql")
        await conn.execute(sql)
        print("✅ Migração executada com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao executar migração: {e}")
    finally:
        if 'conn' in locals():
            await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_migration())
