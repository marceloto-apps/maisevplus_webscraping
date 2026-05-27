import asyncio
import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

async def apply_sql_file(conn, filename: str):
    migration_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations", filename)
    
    if not os.path.exists(migration_path):
        print(f"⚠️  Arquivo não encontrado: {filename}. Pulando.")
        return
        
    print(f"📖 Lendo arquivo: {filename}...")
    with open(migration_path, "r", encoding="utf-8") as f:
        sql = f.read()
        
    print(f"🚀 Executando: {filename}...")
    try:
        # asyncpg execute permite rodar múltiplos comandos separados por ponto e vírgula
        await conn.execute(sql)
        print(f"✅ {filename} aplicado com sucesso!")
    except Exception as e:
        err_msg = str(e)
        if "already exists" in err_msg or "already a member" in err_msg:
            print(f"ℹ️  {filename} já foi aplicado anteriormente (objeto já existe). Pulando.")
        else:
            print(f"❌ Erro ao aplicar {filename}: {e}")

async def main():
    try:
        import asyncpg
    except ImportError:
        print("asyncpg não instalado. Por favor, rode no ambiente virtual (.venv).")
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

    print("🔌 Conectando ao banco de dados...")
    conn = None
    try:
        conn = await asyncpg.connect(dsn=dsn)
        print("🔌 Conectado com sucesso.")
        
        # Enforcar search_path como public
        await conn.execute("SET search_path TO public;")
        
        # Lista das migrações pendentes de qualidade de dados na ordem correta
        pending_files = [
            "018_data_quality_flags.sql",
            "019_odds_quality_flags.sql",
            "019_scraping_health.sql",
            "020_flashscore_extended.sql"
        ]
        
        for sql_file in pending_files:
            await apply_sql_file(conn, sql_file)
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ Erro crítico de conexão/execução: {e}")
    finally:
        if conn:
            await conn.close()
            print("🔌 Conexão encerrada.")

if __name__ == "__main__":
    asyncio.run(main())
