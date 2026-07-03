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
    conn = await asyncpg.connect(dsn=dsn)
    try:
        print("Conectado com sucesso. Iniciando transação...")
        
        # 1. Executar DDL de retrofit_queue e retrofit_match_log
        migration_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations", "023_retrofit_queue.sql")
        
        if not os.path.exists(migration_path):
            print(f"Arquivo nao encontrado: {migration_path}")
            return
            
        with open(migration_path, "r", encoding="utf-8") as f:
            sql = f.read()
            
        print("Executando arquivo de migracao: 023_retrofit_queue.sql")
        await conn.execute(sql)
        print("[OK] Tabelas retrofit_queue e retrofit_match_log criadas com sucesso.")

        # 2. Tentar criar a constraint uq_odds_opening (com time por conta do TimescaleDB)
        # Se falhar (por haver duplicatas ou por regras de partição), apenas capturamos e registramos
        print("\nVerificando se já existe unique constraint cobrindo is_opening...")
        constraint_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'uq_odds_opening'
            )
        """)
        if constraint_exists:
            print("[LOG] Constraint uq_odds_opening já existe na tabela.")
        else:
            try:
                print("Tentando criar constraint uq_odds_opening...")
                await conn.execute("""
                    ALTER TABLE public.odds_history
                    ADD CONSTRAINT uq_odds_opening
                    UNIQUE (match_id, bookmaker_id, market_type, line, period, is_opening, time)
                """)
                print("[OK] Constraint uq_odds_opening criada com sucesso.")
            except Exception as e:
                print(f"[WARN] Nao foi possivel criar unique constraint uq_odds_opening por haver duplicidade ou restrição do TimescaleDB: {e}")

        # 3. Seeding da fila retrofit_queue
        print("\nIniciando seeding da fila retrofit_queue...")
        
        # Definição canônica de prioridades das ligas
        priority_order = [
            1,   # Inglaterra Premier League (league_id=1)
            3,   # Inglaterra Championship (league_id=3)
            4,   # Espanha La Liga (league_id=4)
            25,  # Espanha La Liga 2 (league_id=25)
            2,   # Itália Serie A (league_id=2)
            26,  # Itália Serie B (league_id=26)
            5,   # Alemanha Bundesliga (league_id=5)
            27,  # Alemanha 2. Bundesliga (league_id=27)
            7,   # França Ligue 1 (league_id=7)
            28,  # França Ligue 2 (league_id=28)
            16,  # Portugal Primeira Liga (league_id=16)
            17,  # Holanda Eredivisie (league_id=17)
            8,   # Brasil Série A (league_id=8)
            9,   # Brasil Série B (league_id=9)
        ]
        
        # Buscar todas as ligas que possuem partidas com flashscore_id IS NOT NULL
        leagues = await conn.fetch("""
            SELECT DISTINCT league_id 
            FROM matches 
            WHERE flashscore_id IS NOT NULL
        """)
        
        league_ids = [r['league_id'] for r in leagues]
        
        # Gerar a lista ordenada com prioridades
        seeded_list = []
        priority = 1
        
        # 3.1. Primeiro as prioridades explícitas
        for l_id in priority_order:
            if l_id in league_ids:
                seeded_list.append((l_id, priority))
                priority += 1
                
        # 3.2. Depois as demais ordenadas por league_id ASC
        other_leagues = sorted([l_id for l_id in league_ids if l_id not in priority_order])
        for l_id in other_leagues:
            seeded_list.append((l_id, priority))
            priority += 1
            
        print(f"Total de ligas identificadas para retrofit: {len(seeded_list)}")
        
        # 3.3. Inserir na tabela retrofit_queue calculando total_matches dinamicamente
        inserted_count = 0
        for l_id, prio in seeded_list:
            total_matches = await conn.fetchval("""
                SELECT COUNT(*) 
                FROM matches 
                WHERE league_id = $1 AND flashscore_id IS NOT NULL
            """, l_id)
            
            if total_matches > 0:
                await conn.execute("""
                    INSERT INTO public.retrofit_queue (league_id, priority, status, total_matches)
                    VALUES ($1, $2, 'pending', $3)
                    ON CONFLICT (league_id) DO UPDATE SET
                        priority = EXCLUDED.priority,
                        total_matches = EXCLUDED.total_matches
                """, l_id, prio, total_matches)
                inserted_count += 1
                
        print(f"[OK] Fila retrofit_queue populada com {inserted_count} ligas.")
        
    except Exception as e:
        print(f"[ERROR] Erro ao aplicar migracao/seed: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_migration())
