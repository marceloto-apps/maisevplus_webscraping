"""
scripts/check_actual_odds_status.py

Script para auditoria precisa de quais partidas realmente possuem odds salvas em `odds_history`
e quais foram afetadas erroneamente.
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
        print("AUDITORIA DE ODDS EXISTENTES EM ODDS_HISTORY vs FLAGS DE MATCHES")
        print("=" * 80)

        # 1. Total de matches
        total_matches = await conn.fetchval("SELECT COUNT(*) FROM matches")

        # 2. Total de matches com odds_history (pelo menos 1 odd gravada)
        matches_with_odds = await conn.fetchval("""
            SELECT COUNT(DISTINCT match_id) FROM odds_history
        """)

        # 3. Matches com odds salvas em odds_history MAS que estavam com flashscore_odds_collected = FALSE ou NULL
        matches_with_odds_but_flag_false = await conn.fetchval("""
            SELECT COUNT(DISTINCT m.match_id)
            FROM matches m
            JOIN odds_history oh ON oh.match_id = m.match_id
            WHERE m.flashscore_odds_collected IS NULL OR m.flashscore_odds_collected = FALSE
        """)

        # 4. Matches marcados como scraping_flashscore = TRUE mas que REALMENTE NÃO TÊM nenhuma odd em odds_history
        matches_truly_without_odds = await conn.fetchval("""
            SELECT COUNT(m.match_id)
            FROM matches m
            WHERE m.scraping_flashscore = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM odds_history oh WHERE oh.match_id = m.match_id
              )
        """)

        # 5. Matches que REALMENTE NÃO TÊM nenhuma odd em odds_history (independentemente de scraping_flashscore)
        all_truly_without_odds = await conn.fetchval("""
            SELECT COUNT(m.match_id)
            FROM matches m
            WHERE NOT EXISTS (
                SELECT 1 FROM odds_history oh WHERE oh.match_id = m.match_id
            )
        """)

        print(f"Total de partidas na tabela `matches`:                     {total_matches}")
        print(f"Partidas que TÊM odds salvas em `odds_history`:             {matches_with_odds}")
        print(f"Partidas com odds salvas MAS flag `flashscore_odds_collected` FALSE/NULL: {matches_with_odds_but_flag_false}")
        print(f"Partidas com `scraping_flashscore = TRUE` mas ZERO odds salvas: {matches_truly_without_odds}")
        print(f"Todas as partidas na base com ZERO odds salvas:             {all_truly_without_odds}")
        print("=" * 80)

        # 6. Sincronizar flashscore_odds_collected = TRUE para quem JÁ TEM odds salvas
        if matches_with_odds_but_flag_false > 0:
            print(f"\nSincronizando a flag `flashscore_odds_collected = TRUE` para as {matches_with_odds_but_flag_false} partidas que JÁ possuem odds salvas em `odds_history`...")
            await conn.execute("""
                UPDATE matches m
                SET flashscore_odds_collected = TRUE
                FROM (SELECT DISTINCT match_id FROM odds_history) oh
                WHERE m.match_id = oh.match_id
            """)
            print("✅ Flag `flashscore_odds_collected = TRUE` sincronizada com sucesso para todas as partidas com odds!")

        # 7. Exibir relatório final de partidas reais pendentes de backfill (kickoff no passado, sem odds)
        real_pending = await conn.fetchval("""
            SELECT COUNT(*)
            FROM matches m
            WHERE m.status = 'finished'
              AND m.kickoff <= NOW()
              AND m.flashscore_id IS NOT NULL
              AND (m.scraping_flashscore IS NULL OR m.scraping_flashscore = FALSE)
              AND NOT EXISTS (SELECT 1 FROM odds_history oh WHERE oh.match_id = m.match_id)
        """)
        print(f"\n📌 REAL SALDO PENDENTE DE BACKFILL (Partidas finalizadas no passado sem odds): {real_pending}")
        print("=" * 80)

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
