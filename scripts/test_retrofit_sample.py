"""Script de teste e diagnóstico do retrofit para o usuário executar no terminal.

Uso:
  .venv\\Scripts\\python scripts\\test_retrofit_sample.py
  (ou python3 scripts/test_retrofit_sample.py no Linux)

Este script processa 3 partidas elegíveis e exibe o log detalhado passo-a-passo.
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
    print("TESTE MANUAL DE RETROFIT DE FLASHSCORE (3 PARTIDAS)")
    print("=" * 90)
    
    pool = await get_pool()
    collector = FlashscoreOddsCollector()
    metrics = CollectionMetrics()

    async with pool.acquire() as conn:
        # Buscar 3 partidas elegíveis para retrofit na liga 1 (Premier League) ou na primeira pendente
        matches = await conn.fetch("""
            SELECT m.match_id, m.flashscore_id, m.kickoff, m.league_id
            FROM matches m
            WHERE m.league_id = 1
              AND m.flashscore_id IS NOT NULL
              AND m.kickoff <= NOW()
              AND NOT EXISTS (
                  SELECT 1 FROM odds_history o
                  WHERE o.match_id = m.match_id AND o.is_opening = TRUE
              )
              AND NOT EXISTS (
                  SELECT 1 FROM retrofit_match_log l
                  WHERE l.match_id = m.match_id AND l.status = 'no_opening'
              )
            ORDER BY m.kickoff DESC
            LIMIT 3
        """)

        if not matches:
            print("Nenhuma partida elegível encontrada na Premier League para o teste.")
            await pool.close()
            return

        print(f"Encontradas {len(matches)} partidas elegíveis para o teste:\n")
        for idx, m in enumerate(matches, 1):
            print(f"  {idx}. FS_ID: {m['flashscore_id']} | Kickoff: {m['kickoff'].strftime('%Y-%m-%d %H:%M')}")

        print("\nIniciando execução via Camoufox/Playwright...")
        job_id = f"test_manual_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        async with AsyncCamoufox(headless=True) as browser:
            for idx, m in enumerate(matches, 1):
                m_uuid = m["match_id"]
                fs_id = m["flashscore_id"]
                kickoff = m["kickoff"]

                print(f"\n-----------------------------------------------------------------")
                print(f"[{idx}/{len(matches)}] Processando: {fs_id}")
                print(f"-----------------------------------------------------------------")

                res = await collector.collect_match(
                    browser, conn, m_uuid, fs_id,
                    is_closing=False, job_id=job_id, metrics=metrics,
                    is_prematch=False, kickoff=kickoff, skip_stats=True,
                    skip_closing=True
                )

                inserted_count = res.get("total_inserted", 0)
                markets_ok = res.get("markets_collected", [])
                markets_fail = res.get("markets_failed", [])
                is_complete = res.get("is_complete", False)

                # Verificar no banco se a opening foi gravada em odds_history
                has_opening = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM odds_history
                        WHERE match_id = $1 AND is_opening = TRUE
                    )
                """, m_uuid)

                # Buscar amostra das odds de abertura no banco
                sample_odds = await conn.fetch("""
                    SELECT b.name as bookmaker, o.market_type, o.line, o.odds_1, o.odds_x, o.odds_2
                    FROM odds_history o
                    JOIN bookmakers b ON b.bookmaker_id = o.bookmaker_id
                    WHERE o.match_id = $1 AND o.is_opening = TRUE
                    LIMIT 5
                """, m_uuid)

                print(f"  Resultados para {fs_id}:")
                print(f"    - Opening gravada no DB: {'Sim' if has_opening else 'Nao'}")
                print(f"    - Odds inseridas nesta rodada: {inserted_count}")
                print(f"    - Mercados OK: {markets_ok}")
                print(f"    - Mercados Falhos: {markets_fail}")
                print(f"    - Coleta Completa (1x2 + Over/Under): {is_complete}")

                if sample_odds:
                    print("  Amostra de Odds de Abertura gravadas no banco:")
                    for so in sample_odds:
                        print(f"    * {so['bookmaker']:12s} | Mkt: {so['market_type']:6s} | Line: {str(so['line']):5s} | "
                              f"Odds: {so['odds_1']}/{so['odds_x']}/{so['odds_2']}")

    await pool.close()
    print("\n" + "=" * 90)
    print("TESTE FINALIZADO COM SUCESSO.")
    print("=" * 90)

if __name__ == "__main__":
    asyncio.run(main())
