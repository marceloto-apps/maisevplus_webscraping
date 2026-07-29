"""
scripts/reset_backfill_since_date.py

Reseta o campo `scraping_flashscore = false` na tabela `matches` para partidas
coletadas pelo backfill a partir de uma data específica (default: 2026-07-22 00:00:00).

Uso:
  .venv/bin/python scripts/reset_backfill_since_date.py
  .venv/bin/python scripts/reset_backfill_since_date.py --since-date "2026-07-22 00:00:00"
  .venv/bin/python scripts/reset_backfill_since_date.py --league ENG_L2
"""
import asyncio
import os
import sys
import argparse
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db.logger import configure_logging, get_logger

configure_logging()
logger = get_logger("reset_backfill")

async def main():
    parser = argparse.ArgumentParser(description="Reset scraping_flashscore flag for backfill re-execution")
    parser.add_argument("--since-date", type=str, default="2026-07-22 00:00:00", help="Data/Hora inicial (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--league", type=str, default=None, help="Código da liga (ex: ENG_L2, BRA_SA). Opcional.")
    parser.add_argument("--all-leagues", action="store_true", help="Resetar para todas as ligas desde a data especificada")
    args = parser.parse_args()

    since_str = args.since-date if hasattr(args, "since_date") else args.since_date
    since_dt = datetime.strptime(args.since_date, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    pool = await get_pool()
    async with pool.acquire() as conn:
        print(f"\n[RESET BACKFILL] Buscando partidas marcadas como salvas desde {since_dt}...")

        # 1. Identificar partidas coletadas ou com odds desde since_dt ou com kickoff >= since_dt
        query = """
            SELECT m.match_id, m.flashscore_id, m.kickoff, l.code as league_code, l.name as league_name
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.scraping_flashscore = true
              AND (
                  m.kickoff >= $1
                  OR EXISTS (
                      SELECT 1 FROM odds_history oh 
                      WHERE oh.match_id = m.match_id AND oh.time >= $1
                  )
                  OR EXISTS (
                      SELECT 1 FROM prematch_odds po 
                      WHERE po.match_id = m.match_id AND po.created_at >= $1
                  )
              )
        """
        params = [since_dt]

        if args.league:
            query += " AND l.code = $2"
            params.append(args.league)

        rows = await conn.fetch(query, *params)

        if not rows:
            print(f"❌ Nenhuma partida encontrada atendendo aos critérios desde {args.since_date}.\n")
            await pool.close()
            return

        print(f"Encontradas {len(rows)} partidas para resetar o status de backfill (`scraping_flashscore = false`).")
        
        # Agrupar por liga para relatório
        by_league = {}
        match_ids = [r["match_id"] for r in rows]
        for r in rows:
            code = r["league_code"]
            by_league[code] = by_league.get(code, 0) + 1

        print("\nResumo por liga:")
        for code, count in sorted(by_league.items()):
            print(f"  {code:<12}: {count} partidas")

        # 2. Atualizar matches SET scraping_flashscore = false
        updated = await conn.execute("""
            UPDATE matches
            SET scraping_flashscore = false
            WHERE match_id = ANY($1::uuid[])
        """, match_ids)

        print(f"\n✅ RESET CONCLUÍDO COM SUCESSO! {len(match_ids)} partidas atualizadas para `scraping_flashscore = false`.\n")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
