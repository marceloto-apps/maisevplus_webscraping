"""Script de teste manual do Sequential Backfill para o usuário executar no terminal.

Uso:
  .venv\\Scripts\\python scripts\\test_backfill_sample.py
  (ou python3 scripts/test_backfill_sample.py no Linux)

Este script processa 2 partidas pendentes de backfill (scraping_flashscore = FALSE)
e exibe o log detalhado de coleta de odds e estatísticas.
"""
import asyncio
import os
import sys
import io
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.db.pool import get_pool
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector, CollectionMetrics

async def main():
    print("=" * 90)
    print("TESTE MANUAL DE SEQUENTIAL BACKFILL DO FLASHSCORE (2 PARTIDAS)")
    print("=" * 90)
    
    pool = await get_pool()
    collector = FlashscoreOddsCollector()
    metrics = CollectionMetrics()

    async with pool.acquire() as conn:
        # Buscar 2 partidas pendentes de backfill (scraping_flashscore = FALSE)
        matches = await conn.fetch("""
            SELECT m.match_id, m.flashscore_id, m.kickoff, m.league_id, l.code as league_code
            FROM matches m
            JOIN leagues l ON l.league_id = m.league_id
            WHERE m.league_id = 1
              AND m.status = 'finished'
              AND m.kickoff <= NOW()
              AND m.flashscore_id IS NOT NULL
              AND (m.scraping_flashscore IS NULL OR m.scraping_flashscore = FALSE)
            ORDER BY m.kickoff DESC
            LIMIT 2
        """)

        if not matches:
            print("Nenhuma partida pendente de backfill encontrada no banco de dados.")
            await pool.close()
            return

        print(f"Encontradas {len(matches)} partidas pendentes para o teste de backfill:\n")
        for idx, m in enumerate(matches, 1):
            print(f"  {idx}. FS_ID: {m['flashscore_id']} | Kickoff: {m['kickoff'].strftime('%Y-%m-%d %H:%M')} | Liga: {m['league_code']}")

        print("\nIniciando execução via Camoufox/Playwright...")
        job_id = f"test_backfill_manual_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        async with AsyncCamoufox(headless=True) as browser:
            for idx, m in enumerate(matches, 1):
                m_uuid = m["match_id"]
                fs_id = m["flashscore_id"]
                kickoff = m["kickoff"]
                league_code = m["league_code"]

                print(f"\n-----------------------------------------------------------------")
                print(f"[{idx}/{len(matches)}] Processando Backfill: {fs_id} (Liga: {league_code})")
                print(f"-----------------------------------------------------------------")

                res = await collector.collect_match(
                    browser=browser,
                    conn=conn,
                    match_id_uuid=str(m_uuid),
                    flashscore_id=fs_id,
                    is_closing=True,
                    job_id=job_id,
                    metrics=metrics,
                    kickoff=kickoff,
                    skip_stats=False
                )

                inserted_count = res.get("total_inserted", 0)
                markets_ok = res.get("markets_collected", [])
                markets_fail = res.get("markets_failed", [])
                is_complete = res.get("is_complete", False)

                # Marcar partida como processada no banco
                await conn.execute("UPDATE matches SET scraping_flashscore = TRUE WHERE match_id = $1", m_uuid)

                # Checar placares e stats salvos
                m_info = await conn.fetchrow("""
                    SELECT ft_home, ft_away, ht_home, ht_away, flashscore_odds_collected, flashscore_stats_collected
                    FROM matches WHERE match_id = $1
                """, m_uuid)

                # Checar odds gravadas
                odds_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM odds_history WHERE match_id = $1
                """, m_uuid)

                print(f"  Resultados do Backfill para {fs_id}:")
                print(f"    - Placares: FT={m_info['ft_home']}-{m_info['ft_away']} | HT={m_info['ht_home']}-{m_info['ht_away']}")
                print(f"    - Odds salvas no DB (total): {odds_count}")
                print(f"    - Scraping Flashscore Concluído: True")
                print(f"    - Flashscore Stats Coletados: {m_info['flashscore_stats_collected']}")
                print(f"    - Mercados de Odds OK: {markets_ok}")
                print(f"    - Mercados Falhos: {markets_fail}")

                # Amostra das odds salvas
                sample_odds = await conn.fetch("""
                    SELECT b.name as bookmaker, o.market_type, o.line, o.odds_1, o.odds_x, o.odds_2, o.is_opening
                    FROM odds_history o
                    JOIN bookmakers b ON b.bookmaker_id = o.bookmaker_id
                    WHERE o.match_id = $1
                    ORDER BY o.is_opening DESC, b.name ASC
                    LIMIT 6
                """, m_uuid)

                if sample_odds:
                    print("  Amostra de Odds gravadas no banco (Abertura e Fechamento):")
                    for so in sample_odds:
                        tipo = "Abertura" if so['is_opening'] else "Fechamento"
                        print(f"    * [{tipo:10s}] {so['bookmaker']:12s} | Mkt: {so['market_type']:6s} | Line: {str(so['line']):5s} | "
                              f"Odds: {so['odds_1']}/{so['odds_x']}/{so['odds_2']}")

    await pool.close()
    print("\n" + "=" * 90)
    print("TESTE DE BACKFILL FINALIZADO COM SUCESSO.")
    print("=" * 90)

if __name__ == "__main__":
    asyncio.run(main())
