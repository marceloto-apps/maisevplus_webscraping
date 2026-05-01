"""
Verifica o estado dos jobs de scraping via DB - logs recentes e crontab jobs
"""
import asyncio
import asyncpg
from datetime import datetime, timezone

async def check():
    conn = await asyncpg.connect(
        user="maisevplus", password="s32LSremnxBs",
        database="maisevplus_db", host="127.0.0.1", port=5432
    )

    # Verificar se existe tabela de job log / scraping_log
    tables = await conn.fetch("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    print("=== TABELAS NO BANCO ===")
    for t in tables:
        print(f"  {t['table_name']}")

    # Verificar scraping_log se existir
    has_log = any(t['table_name'] == 'scraping_log' for t in tables)
    has_job_log = any(t['table_name'] == 'job_log' for t in tables)
    
    if has_log:
        rows = await conn.fetch("""
            SELECT * FROM scraping_log 
            ORDER BY created_at DESC LIMIT 20
        """)
        print("\n=== SCRAPING_LOG (últimos 20) ===")
        for r in rows:
            print(dict(r))

    if has_job_log:
        rows = await conn.fetch("""
            SELECT * FROM job_log 
            ORDER BY created_at DESC LIMIT 20
        """)
        print("\n=== JOB_LOG (últimos 20) ===")
        for r in rows:
            print(dict(r))

    # Agora vamos ver a faixa de kickoff das partidas pendentes para entender qual janela rodou
    r2 = await conn.fetchrow("""
        SELECT 
            MIN(m.kickoff) AS min_kickoff,
            MAX(m.kickoff) AS max_kickoff
        FROM matches m
        WHERE m.scraping_flashscore = true AND m.flashscore_id IS NOT NULL
    """)
    print(f"\n=== FAIXA DE KICKOFF DAS PARTIDAS JA COLETADAS ===")
    print(f"  Mais antiga: {r2['min_kickoff']}")
    print(f"  Mais recente: {r2['max_kickoff']}")

    r3 = await conn.fetchrow("""
        SELECT 
            MIN(m.kickoff) AS min_kickoff,
            MAX(m.kickoff) AS max_kickoff
        FROM matches m
        WHERE (m.scraping_flashscore IS NULL OR m.scraping_flashscore = false)
          AND m.flashscore_id IS NOT NULL
          AND m.status = 'finished'
    """)
    print(f"\n=== FAIXA DE KICKOFF DAS PENDENTES ===")
    print(f"  Mais antiga: {r3['min_kickoff']}")
    print(f"  Mais recente: {r3['max_kickoff']}")

    await conn.close()

asyncio.run(check())
