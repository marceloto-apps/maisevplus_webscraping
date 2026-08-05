"""
scripts/reset_failed_flashscore_matches.py

Script para identificar e resetar partidas do Flashscore que foram marcadas como processadas
(`scraping_flashscore = true`) durante a janela de erro onde as odds não foram coletadas
(`flashscore_odds_collected = false` ou 0 odds gravadas no banco).

Uso:
  .venv/bin/python scripts/reset_failed_flashscore_matches.py [--dry-run]
"""
import asyncio
import os
import sys
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

async def main():
    parser = argparse.ArgumentParser(description="Reset failed/incomplete Flashscore matches for backfill retry")
    parser.add_argument("--dry-run", action="store_true", help="Apenas exibe as partidas sem alterar o banco")
    args = parser.parse_args()

    pool = await get_pool()
    async with pool.acquire() as conn:
        print("\n" + "=" * 80)
        print("INSPEÇÃO E RESET DE PARTIDAS DO BACKFILL FLASHSCORE")
        print("=" * 80)

        # 1. Partidas com scraping_flashscore = TRUE mas flashscore_odds_collected = FALSE (ou NULL)
        rows = await conn.fetch("""
            SELECT m.match_id, m.flashscore_id, m.kickoff, l.code as league_code,
                   m.flashscore_stats_collected, m.flashscore_odds_collected
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.scraping_flashscore = TRUE
              AND (m.flashscore_odds_collected IS NULL OR m.flashscore_odds_collected = FALSE)
            ORDER BY m.kickoff DESC
        """)

        print(f"\n[1] Partidas marcadas como `scraping_flashscore = TRUE` mas SEM odds coletadas/salvas: {len(rows)}")

        if rows:
            by_league = {}
            for r in rows:
                code = r["league_code"]
                by_league[code] = by_league.get(code, 0) + 1

            print("   Distribuição por liga:")
            for code, count in sorted(by_league.items()):
                print(f"     - {code:<12}: {count} partidas")

            print("\n   Exemplo das 5 partidas mais recentes encontradas:")
            for r in rows[:5]:
                print(f"     * FS_ID: {r['flashscore_id']} | Kickoff: {r['kickoff'].strftime('%Y-%m-%d %H:%M')} | "
                      f"Liga: {r['league_code']} | Stats: {r['flashscore_stats_collected']} | "
                      f"Odds: {r['flashscore_odds_collected']}")

            match_ids = [r["match_id"] for r in rows]

            if args.dry_run:
                print("\n[DRY RUN] Nenhuma alteração realizada no banco de dados.")
            else:
                updated = await conn.execute("""
                    UPDATE matches
                    SET scraping_flashscore = FALSE,
                        flashscore_odds_collected = FALSE
                    WHERE match_id = ANY($1::uuid[])
                """, match_ids)
                print(f"\n✅ RESET CONCLUÍDO: {len(match_ids)} partidas atualizadas para `scraping_flashscore = FALSE` e `flashscore_odds_collected = FALSE`.")
                print("   Elas serão reprocessadas automaticamente na próxima rodada do Sequential Backfill!")
        else:
            print("   Nenhuma partida encontrada com `scraping_flashscore = TRUE` e odds incompletas.")

    await pool.close()
    print("=" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
