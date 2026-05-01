"""
Consulta ingestion_log para ver atividade do backfill flashscore na madrugada
"""
import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect(
        user="maisevplus", password="s32LSremnxBs",
        database="maisevplus_db", host="127.0.0.1", port=5432
    )

    # Estrutura da tabela ingestion_log
    cols = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'ingestion_log'
        ORDER BY ordinal_position
    """)
    print("=== COLUNAS ingestion_log ===")
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']})")

    # Últimos registros das últimas 8 horas
    rows = await conn.fetch("""
        SELECT *
        FROM ingestion_log
        WHERE created_at >= NOW() - INTERVAL '8 hours'
        ORDER BY created_at DESC
        LIMIT 50
    """)
    print(f"\n=== INGESTION_LOG (últimas 8h) — {len(rows)} registros ===")
    for r in rows:
        print(dict(r))

    # Resumo por job_id nas últimas 24h
    rows2 = await conn.fetch("""
        SELECT job_id, source, COUNT(*) as n, MIN(created_at) as inicio, MAX(created_at) as fim
        FROM ingestion_log
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        GROUP BY job_id, source
        ORDER BY inicio DESC
    """)
    print(f"\n=== RESUMO POR JOB (últimas 24h) ===")
    for r in rows2:
        print(f"  job={r['job_id']} source={r['source']} n={r['n']} inicio={r['inicio']} fim={r['fim']}")

    await conn.close()

asyncio.run(check())
