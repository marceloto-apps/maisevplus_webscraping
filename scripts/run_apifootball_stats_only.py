"""
scripts/run_apifootball_stats_only.py

Script para re-coletar APENAS o endpoint /fixtures/statistics da API-Football.
Baseado no run_apifootball_backfill.py, percorre as ligas da temporada atual,
puxa os fixtures, resolve para match_id no banco e coleta stats onde faltam.

Usa blocked_shots_home IS NULL como indicador de que o endpoint /statistics
não rodou para aquela partida.
"""

import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db.logger import get_logger
from src.normalizer.team_resolver import TeamResolver
from src.collectors.api_football.client import ApiFootballClient
from src.collectors.api_football.stats_collector import StatsCollector

logger = get_logger("apifb_stats_only")

BRT = ZoneInfo("America/Sao_Paulo")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STATE_FILE = os.path.join(DATA_DIR, "apifootball_stats_only_state.json")

MAX_REQUESTS_PER_RUN = 1500
SKIP_LEAGUES = {"ENG_NL"}  # Ligas sem estatísticas no API-Football


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "completed_leagues": [],
        "last_processed_fixture_id": None
    }


def save_state(state: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


async def get_active_leagues(pool) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT l.league_id, l.code, l.api_football_league_id, CAST(LEFT(s.label, 4) AS INTEGER) AS year 
            FROM seasons s 
            JOIN leagues l ON s.league_id = l.league_id 
            WHERE s.is_current = TRUE AND l.api_football_league_id IS NOT NULL
        ''')

    active_leagues = [dict(r) for r in rows]
    bra = [l for l in active_leagues if l["code"] == "BRA_SA"]
    others = [l for l in active_leagues if l["code"] != "BRA_SA"]
    others.sort(key=lambda x: x["code"])

    return bra + others


async def has_stats(pool, match_id: str) -> bool:
    """Retorna True se o endpoint /statistics já rodou para esta partida."""
    async with pool.acquire() as conn:
        return bool(await conn.fetchval(
            "SELECT 1 FROM match_stats WHERE match_id = $1 AND blocked_shots_home IS NOT NULL LIMIT 1",
            match_id
        ))


async def resolve_fixture_to_match(pool, fixture: dict, league_id: int) -> dict | None:
    fi_date_str = fixture["fixture"]["date"]
    raw_dt = datetime.fromisoformat(fi_date_str)
    kickoff_brt = raw_dt.astimezone(BRT)
    kickoff_d = kickoff_brt.date()

    home_name = fixture["teams"]["home"]["name"]
    away_name = fixture["teams"]["away"]["name"]
    af_fixture_id = fixture["fixture"]["id"]

    home_api_id = fixture["teams"]["home"]["id"]
    away_api_id = fixture["teams"]["away"]["id"]

    async with pool.acquire() as conn:
        home_db_id = await conn.fetchval("SELECT team_id FROM teams WHERE api_football_id = $1", home_api_id)
        away_db_id = await conn.fetchval("SELECT team_id FROM teams WHERE api_football_id = $1", away_api_id)

    if home_db_id is None:
        home_db_id = await TeamResolver.resolve("api_football", home_name)
    if away_db_id is None:
        away_db_id = await TeamResolver.resolve("api_football", away_name)

    if home_db_id is None or away_db_id is None:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT match_id FROM matches
            WHERE home_team_id = $1
              AND away_team_id = $2
              AND kickoff::date BETWEEN $3 AND $4
              AND league_id = $5
            ORDER BY kickoff
            LIMIT 1
            """,
            home_db_id, away_db_id,
            kickoff_d - timedelta(days=1),
            kickoff_d + timedelta(days=1),
            league_id
        )

    if row is None:
        return None

    return {
        "match_id": row["match_id"],
        "api_football_id": af_fixture_id,
        "home_team_id": home_db_id,
        "away_team_id": away_db_id,
        "home_api_id": home_api_id,
        "away_api_id": away_api_id,
        "home_name": home_name,
        "away_name": away_name,
        "kickoff_brt": kickoff_brt
    }


async def run():
    print("\n" + "=" * 55)
    print("   API-FOOTBALL — STATS ONLY BACKFILL")
    print("=" * 55 + "\n")

    pool = await get_pool()
    await TeamResolver.load_cache()

    leagues = await get_active_leagues(pool)
    state = load_state()
    completed_leagues = state.get("completed_leagues", [])
    last_fixture_id = state.get("last_processed_fixture_id")
    reqs_used = 0

    stats_c = StatsCollector()

    for l_data in leagues:
        l_code = l_data["code"]
        l_api_id = l_data["api_football_league_id"]
        l_year = l_data["year"]
        l_db_id = l_data["league_id"]

        if l_code in completed_leagues:
            continue

        if l_code in SKIP_LEAGUES:
            print(f"⏭ [{l_code}] Pulando (sem stats no API-Football).")
            continue

        print(f"▶ [{l_code}] Puxando fixtures {l_year}...")
        try:
            fixtures = await ApiFootballClient.get("/fixtures", {"league": l_api_id, "season": l_year})
            reqs_used += 1
        except Exception as e:
            msg = f"ERRO ao puxar /fixtures da {l_code}: {e}"
            logger.error(msg)
            print(msg)
            break

        if not fixtures:
            print(f"   ↳ 0 resultados.")
            continue

        # Filtro: match status concluído, data BRT <= 2026-04-03
        target_max_date = date(2026, 4, 3)
        valid = []
        for f in fixtures:
            if f["fixture"]["status"]["short"] not in ("FT", "AET", "PEN"):
                continue

            raw_dt = datetime.fromisoformat(f["fixture"]["date"])
            k_d = raw_dt.astimezone(BRT).date()
            if k_d <= target_max_date:
                valid.append((f, raw_dt.timestamp()))

        # Ordernar descendente por timestamp (do mais novo para o mais antigo)
        valid.sort(key=lambda x: x[1], reverse=True)
        sorted_fixtures = [x[0] for x in valid]

        print(f"   ↳ {len(sorted_fixtures)} jogos a avaliar (<= 03/04).")

        stats_collected = 0
        stats_skipped = 0

        for f in sorted_fixtures:
            if reqs_used >= MAX_REQUESTS_PER_RUN:
                break

            f_id = f["fixture"]["id"]

            # Checa se precisamos retomar a partir de um fixture_id específico
            if last_fixture_id and last_fixture_id == f_id:
                last_fixture_id = None
                continue
            elif last_fixture_id:
                continue

            m = await resolve_fixture_to_match(pool, f, l_db_id)
            if not m:
                continue

            mid = str(m["match_id"])

            # Checa se já tem stats
            if await has_stats(pool, mid):
                stats_skipped += 1
                state["last_processed_fixture_id"] = f_id
                continue

            label = f"{m['home_name']} x {m['away_name']} ({m['kickoff_brt'].strftime('%d/%m')})"
            team_map = {
                m["home_api_id"]: m["home_team_id"],
                m["away_api_id"]: m["away_team_id"],
            }

            sys.stdout.write(f"    ➜ Stats: {label}...")
            sys.stdout.flush()

            try:
                await stats_c.collect(mid, m["api_football_id"], team_map)
                reqs_used += 1
                stats_collected += 1
                print(f" ✅ (+1 req) | Total: {reqs_used}/{MAX_REQUESTS_PER_RUN}")
            except Exception as e:
                reqs_used += 1
                logger.error("stats_only_err", match_id=mid, error=str(e))
                print(f" ❌ {e}")

            state["last_processed_fixture_id"] = f_id
            save_state(state)

        if reqs_used >= MAX_REQUESTS_PER_RUN:
            print(f"\n[!] LIMITE DE {MAX_REQUESTS_PER_RUN} REQUESTS ATINGIDO. Pausando.")
            break
        else:
            completed_leagues.append(l_code)
            state["completed_leagues"] = completed_leagues
            state["last_processed_fixture_id"] = None
            save_state(state)
            print(f"   ↳ Coletados: {stats_collected} | Skipped: {stats_skipped}")
            print(f"✅ Liga {l_code} inteiramente concluída.")

    print(f"\nExecução finalizada. Total requests: {reqs_used}")


if __name__ == "__main__":
    asyncio.run(run())
