"""
scripts/run_apifootball_stats_only.py

Script para re-coletar APENAS o endpoint /fixtures/statistics da API-Football
para partidas que já possuem events/lineups/players mas faltam as stats detalhadas
(blocked_shots, shots_insidebox, passes_accurate, etc.).

Identifica automaticamente no banco as partidas com lacuna de stats.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db.logger import get_logger
from src.normalizer.team_resolver import TeamResolver
from src.collectors.api_football.client import ApiFootballClient
from src.collectors.api_football.stats_collector import StatsCollector

logger = get_logger("apifb_stats_only")

MAX_REQUESTS = 7200  # margem de segurança no plano VIP


async def find_missing_stats(pool) -> list:
    """
    Encontra partidas que têm match_events (prova de que o backfill rodou)
    mas cujo blocked_shots_home está NULL em match_stats
    (prova de que o endpoint /statistics NÃO rodou).
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT m.match_id, m.api_football_id, m.home_team_id, m.away_team_id,
                   th.name AS home_name, ta.name AS away_name, m.kickoff
            FROM matches m
            JOIN match_events me ON me.match_id = m.match_id
            JOIN match_stats ms ON ms.match_id = m.match_id
            JOIN teams th ON th.team_id = m.home_team_id
            JOIN teams ta ON ta.team_id = m.away_team_id
            WHERE m.api_football_id IS NOT NULL
              AND ms.blocked_shots_home IS NULL
            ORDER BY m.kickoff DESC
        """)
    return [dict(r) for r in rows]


async def run():
    print("\n" + "=" * 55)
    print("   API-FOOTBALL — STATS ONLY BACKFILL")
    print("=" * 55 + "\n")

    pool = await get_pool()
    await TeamResolver.load_cache()

    missing = await find_missing_stats(pool)
    print(f"📋 Partidas com stats faltando: {len(missing)}\n")

    if not missing:
        print("✅ Nenhuma partida pendente. Tudo OK!")
        return

    stats_c = StatsCollector()
    reqs = 0
    ok_count = 0
    err_count = 0

    for row in missing:
        if reqs >= MAX_REQUESTS:
            print(f"\n[!] LIMITE DE {MAX_REQUESTS} REQUESTS ATINGIDO. Pausando.")
            break

        mid = str(row["match_id"])
        fid = row["api_football_id"]
        label = f"{row['home_name']} x {row['away_name']} ({row['kickoff'].strftime('%d/%m/%Y')})"

        # Precisamos do mapeamento api_football_team_id -> db_team_id
        # Buscamos os api_football_id dos times
        async with pool.acquire() as conn:
            home_api_id = await conn.fetchval(
                "SELECT api_football_id FROM teams WHERE team_id = $1", row["home_team_id"]
            )
            away_api_id = await conn.fetchval(
                "SELECT api_football_id FROM teams WHERE team_id = $1", row["away_team_id"]
            )

        team_map = {}
        if home_api_id:
            team_map[home_api_id] = row["home_team_id"]
        if away_api_id:
            team_map[away_api_id] = row["away_team_id"]

        sys.stdout.write(f"  ➜ Stats: {label}...")
        sys.stdout.flush()

        try:
            result = await stats_c.collect(mid, fid, team_map)
            reqs += 1
            if result.status.value == "success":
                ok_count += 1
                print(f" ✅ (+1 req) | Total: {reqs}")
            else:
                err_count += 1
                print(f" ⚠ FALHOU | Total: {reqs}")
        except Exception as e:
            err_count += 1
            reqs += 1  # a request provavelmente foi feita mesmo com erro
            print(f" ❌ {e}")

    print(f"\n{'=' * 55}")
    print(f"  RESULTADO:")
    print(f"    ✅ Sucesso:  {ok_count}")
    print(f"    ❌ Erros:    {err_count}")
    print(f"    📡 Requests: {reqs}")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    asyncio.run(run())
