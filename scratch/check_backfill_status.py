import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def check():
    conn = await asyncpg.connect(
        user="maisevplus", password="s32LSremnxBs",
        database="maisevplus_db", host="127.0.0.1", port=5432
    )

    # Progresso geral
    r = await conn.fetchrow("""
        SELECT 
            COUNT(*) FILTER (WHERE scraping_flashscore = true)  AS coletadas,
            COUNT(*) FILTER (WHERE scraping_flashscore IS NULL OR scraping_flashscore = false) AS pendentes,
            COUNT(*) AS total
        FROM matches
        WHERE status = 'finished' AND flashscore_id IS NOT NULL
    """)
    print("=== PROGRESSO BACKFILL FLASHSCORE ===")
    print(f"  Coletadas (scraping_flashscore=true): {r['coletadas']}")
    print(f"  Pendentes:                            {r['pendentes']}")
    print(f"  Total com flashscore_id:              {r['total']}")

    # Por liga
    rows_league = await conn.fetch("""
        SELECT l.code,
               COUNT(*) FILTER (WHERE m.scraping_flashscore = true) AS coletadas,
               COUNT(*) FILTER (WHERE m.scraping_flashscore IS NULL OR m.scraping_flashscore = false) AS pendentes,
               COUNT(*) AS total
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.status = 'finished' AND m.flashscore_id IS NOT NULL
        GROUP BY l.code
        ORDER BY pendentes DESC, l.code
    """)
    print("\n=== POR LIGA ===")
    print(f"  {'LIGA':<12} {'COLETADAS':>10} {'PENDENTES':>10} {'TOTAL':>8}")
    print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*8}")
    for row in rows_league:
        print(f"  {row['code']:<12} {row['coletadas']:>10} {row['pendentes']:>10} {row['total']:>8}")

    # Últimas 10 coletadas - para ver quando parou
    rows_last = await conn.fetch("""
        SELECT m.flashscore_id, l.code, m.kickoff
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.scraping_flashscore = true AND m.flashscore_id IS NOT NULL
        ORDER BY m.kickoff DESC
        LIMIT 10
    """)
    print("\n=== ÚLTIMAS 10 PARTIDAS COLETADAS (mais recentes por kickoff) ===")
    for row in rows_last:
        print(f"  [{row['code']}] fs_id={row['flashscore_id']}  kickoff={row['kickoff']}")

    await conn.close()

asyncio.run(check())
