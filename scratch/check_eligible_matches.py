"""
Script auxiliar para consultar quais partidas seriam processadas e qual a data delas.
Mostra as 10 primeiras partidas elegíveis para verificar se são recentes ou antigas.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db.logger import configure_logging, get_logger

configure_logging()
logger = get_logger("check_eligible")


async def check_eligible(league_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Quais são as primeiras partidas que o retrofit processaria?
        matches = await conn.fetch("""
            SELECT m.match_id, m.flashscore_id, m.kickoff,
                   ht.name AS home_team, at.name AS away_team
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.league_id = $1
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
            LIMIT 20
        """, league_id)

        print(f"\n{'='*100}")
        print(f"TOP 20 partidas elegíveis para retrofit (Liga {league_id}) — Ordem: mais recentes primeiro")
        print(f"{'='*100}")
        for i, m in enumerate(matches):
            age = (datetime.now(timezone.utc) - m['kickoff'].replace(tzinfo=timezone.utc)).days
            print(f"  {i+1:2d}. {m['flashscore_id']} | {m['kickoff'].strftime('%Y-%m-%d %H:%M')} | {m['home_team']} vs {m['away_team']} | {age}d atrás")
        
        total = await conn.fetchval("""
            SELECT COUNT(*)
            FROM matches m
            WHERE m.league_id = $1
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
        """, league_id)
        print(f"\nTotal elegíveis: {total}")
        
        # Verificar também partidas recentes COM odds (para confirmar que tínhamos antes)
        recent_with_odds = await conn.fetch("""
            SELECT m.flashscore_id, m.kickoff, ht.name, at.name,
                   COUNT(DISTINCT o.bookmaker_id) as n_bookmakers
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN odds_history o ON o.match_id = m.match_id AND o.is_opening = TRUE
            WHERE m.league_id = $1
            GROUP BY m.flashscore_id, m.kickoff, ht.name, at.name
            ORDER BY m.kickoff DESC
            LIMIT 5
        """, league_id)
        
        print(f"\n{'='*100}")
        print(f"Últimas 5 partidas COM opening odds gravadas (Liga {league_id})")
        print(f"{'='*100}")
        for m in recent_with_odds:
            print(f"  {m['flashscore_id']} | {m['kickoff'].strftime('%Y-%m-%d %H:%M')} | {m['name']} vs {m[3]} | {m['n_bookmakers']} bookmakers")
        
        if not recent_with_odds:
            print("  (Nenhuma partida com opening odds encontrada!)")
        
        # Também verificar a Premier League (para ter uma comparação)
        pl_matches = await conn.fetch("""
            SELECT m.flashscore_id, m.kickoff, ht.name, at.name
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.league_id = (SELECT league_id FROM leagues WHERE code = 'ENG_PL' LIMIT 1)
              AND m.flashscore_id IS NOT NULL
              AND m.kickoff <= NOW()
              AND NOT EXISTS (
                  SELECT 1 FROM odds_history o
                  WHERE o.match_id = m.match_id AND o.is_opening = TRUE
              )
            ORDER BY m.kickoff DESC
            LIMIT 5
        """)
        
        print(f"\n{'='*100}")
        print(f"Premier League — últimas 5 partidas SEM opening odds (para teste comparativo)")
        print(f"{'='*100}")
        for m in pl_matches:
            age = (datetime.now(timezone.utc) - m['kickoff'].replace(tzinfo=timezone.utc)).days
            print(f"  {m['flashscore_id']} | {m['kickoff'].strftime('%Y-%m-%d %H:%M')} | {m['name']} vs {m[3]} | {age}d atrás")
        
        if not pl_matches:
            print("  (Todas as partidas da PL já têm opening odds!)")
        
        print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--league-id", type=int, default=4)
    args = parser.parse_args()
    asyncio.run(check_eligible(args.league_id))
