"""
scripts/reset_failed_backfill_clean.py

Reseta o campo `scraping_flashscore = FALSE` para as partidas que foram marcadas
como `scraping_flashscore = TRUE` mas que REALMENTE não possuem nenhuma odd salva em `odds_history`.
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("=" * 80)
        print("RESET DE PARTIDAS FALHAS SEM ODDS EM ODDS_HISTORY")
        print("=" * 80)

        # 1. Identificar partidas com scraping_flashscore = TRUE mas sem odds em odds_history
        rows = await conn.fetch("""
            SELECT m.match_id, m.flashscore_id, m.kickoff, l.code as league_code
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.scraping_flashscore = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM odds_history oh WHERE oh.match_id = m.match_id
              )
        """)

        print(f"Partidas encontradas com `scraping_flashscore = TRUE` e ZERO odds salvas: {len(rows)}")

        if rows:
            by_league = {}
            for r in rows:
                code = r["league_code"]
                by_league[code] = by_league.get(code, 0) + 1

            print("\nDistribuição por liga:")
            for code, count in sorted(by_league.items()):
                print(f"  - {code:<12}: {count} partidas")

            match_ids = [r["match_id"] for r in rows]
            await conn.execute("""
                UPDATE matches
                SET scraping_flashscore = FALSE,
                    flashscore_odds_collected = FALSE
                WHERE match_id = ANY($1::uuid[])
            """, match_ids)
            print(f"\n✅ RESET CONCLUÍDO COM SUCESSO: {len(match_ids)} partidas atualizadas para `scraping_flashscore = FALSE`.")
        else:
            print("Nenhuma partida pendente de reset.")

        # Re-conferir o saldo pendente do backfill
        pending = await conn.fetchval("""
            SELECT COUNT(*)
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            WHERE l.is_active = TRUE
              AND m.status = 'finished'
              AND m.kickoff <= NOW()
              AND m.flashscore_id IS NOT NULL
              AND (m.scraping_flashscore IS NULL OR m.scraping_flashscore = FALSE)
              AND NOT EXISTS (SELECT 1 FROM odds_history oh WHERE oh.match_id = m.match_id)
        """)
        print(f"\n📌 TOTAL DE PARTIDAS PRONTAS PARA O SEQUENTIAL BACKFILL: {pending}")
        print("=" * 80)

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
