"""
scripts/run_apifootball_backfill_prev_season.py

Backfill da API-Football para a TEMPORADA ANTERIOR (a mais recente não-current).
  - Mesmo fluxo do backfill principal, mas busca a temporada anterior no banco.
  - Para cada liga, consome 1 request para puxar /fixtures da season anterior.
  - Filtra jogos concluídos (FT/AET/PEN).
  - Ordena do mais recente para o mais antigo.
  - Pula partidas que já possuem stats+events+lineups+players.
  - Usa 4 reqs (Stats/Events/Lineups/Players) para preencher cada partida.
  - Pula ENG_NL (sem stats no API-Football).
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db.logger import get_logger
from src.normalizer.team_resolver import TeamResolver
from src.collectors.api_football.client import ApiFootballClient
from src.collectors.api_football.stats_collector import StatsCollector
from src.collectors.api_football.events_collector import EventsCollector
from src.collectors.api_football.lineup_collector import LineupCollector
from src.collectors.api_football.players_collector import PlayersCollector

logger = get_logger("apifb_backfill_prev")

BRT = ZoneInfo("America/Sao_Paulo")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STATE_FILE = os.path.join(DATA_DIR, "apifootball_backfill_prev_state.json")

MAX_REQUESTS_PER_RUN = 1450
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


async def get_previous_season_leagues(pool) -> list:
    """
    Busca a temporada anterior (a mais recente que NÃO é is_current)
    para cada liga que tem api_football_league_id.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT l.league_id, l.code, l.api_football_league_id, 
                   CAST(LEFT(s.label, 4) AS INTEGER) AS year,
                   s.label
            FROM seasons s
            JOIN leagues l ON s.league_id = l.league_id
            WHERE s.is_current = FALSE
              AND l.api_football_league_id IS NOT NULL
              AND s.season_id = (
                  SELECT s2.season_id FROM seasons s2
                  WHERE s2.league_id = l.league_id
                    AND s2.is_current = FALSE
                  ORDER BY s2.start_date DESC
                  LIMIT 1
              )
        ''')

    leagues = [dict(r) for r in rows]
    bra = [l for l in leagues if l["code"] == "BRA_SA"]
    others = [l for l in leagues if l["code"] != "BRA_SA"]
    others.sort(key=lambda x: x["code"])

    return bra + others


async def get_match_status(pool, match_id: str) -> dict:
    """Retorna o status de coleta de cada parte para não gastar cotas em duplicidade."""
    status = {"stats": False, "events": False, "lineups": False, "players": False}
    async with pool.acquire() as conn:
        status["stats"] = bool(await conn.fetchval("SELECT 1 FROM match_stats WHERE match_id = $1 AND total_passes_home IS NOT NULL LIMIT 1", match_id))
        status["events"] = bool(await conn.fetchval("SELECT 1 FROM match_events WHERE match_id = $1 LIMIT 1", match_id))
        status["lineups"] = bool(await conn.fetchval("SELECT 1 FROM lineups WHERE match_id = $1 LIMIT 1", match_id))
        status["players"] = bool(await conn.fetchval("SELECT 1 FROM match_player_stats WHERE match_id = $1 LIMIT 1", match_id))
    return status


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
        print(f"    ⚠ Não resolvido: {home_name} x {away_name} ({home_api_id} / {away_api_id})")
        return None

    # +- 1 dia para fuso horário
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
        print(f"    ⚠ Match DB = NULL: db_teams {home_db_id} x {away_db_id} perto de {kickoff_d}.")
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


async def process_match(m: dict, status: dict, stats_c, events_c, lineups_c, players_c, pool) -> int:
    mid = str(m["match_id"])
    fid = m["api_football_id"]
    team_map = {
        m["home_api_id"]: m["home_team_id"],
        m["away_api_id"]: m["away_team_id"],
    }

    req_count = 0

    if not status["stats"]:
        try:
            await stats_c.collect(mid, fid, team_map)
            req_count += 1
        except Exception as e:
            logger.error(f"stats_err", match_id=mid, error=str(e))

    if not status["events"]:
        try:
            await events_c.collect(mid, fid, team_map)
            req_count += 1
        except Exception as e:
            logger.error(f"events_err", match_id=mid, error=str(e))

    if not status["lineups"]:
        try:
            await lineups_c.collect(mid, fid, team_map)
            req_count += 1
        except Exception as e:
            logger.error(f"lineups_err", match_id=mid, error=str(e))

    if not status["players"]:
        try:
            await players_c.collect(mid, fid, team_map)
            req_count += 1
        except Exception as e:
            logger.error(f"players_err", match_id=mid, error=str(e))

    async with pool.acquire() as conn:
        await conn.execute("UPDATE matches SET api_football_id = $1 WHERE match_id = $2", fid, m["match_id"])

    return req_count


async def run():
    print("\n" + "=" * 55)
    print("   API-FOOTBALL BACKFILL — TEMPORADA ANTERIOR")
    print("=" * 55 + "\n")

    pool = await get_pool()
    await TeamResolver.load_cache()

    leagues = await get_previous_season_leagues(pool)
    print(f"📋 {len(leagues)} ligas com temporada anterior encontradas.\n")

    state = load_state()
    completed_leagues = state.get("completed_leagues", [])
    last_fixture_id = state.get("last_processed_fixture_id")
    reqs_used = 0

    stats_c = StatsCollector()
    events_c = EventsCollector()
    lineups_c = LineupCollector()
    players_c = PlayersCollector()

    for l_data in leagues:
        l_code = l_data["code"]
        l_api_id = l_data["api_football_league_id"]
        l_year = l_data["year"]
        l_db_id = l_data["league_id"]
        l_label = l_data["label"]

        if l_code in completed_leagues:
            continue

        if l_code in SKIP_LEAGUES:
            print(f"⏭ [{l_code}] Pulando (sem stats no API-Football).")
            continue

        print(f"▶ [{l_code}] Puxando fixtures da temporada {l_label} (year={l_year})...")
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

        # Filtro: match status concluído (sem filtro de data — queremos toda a temporada)
        valid = []
        for f in fixtures:
            if f["fixture"]["status"]["short"] not in ("FT", "AET", "PEN"):
                continue

            raw_dt = datetime.fromisoformat(f["fixture"]["date"])
            valid.append((f, raw_dt.timestamp()))

        # Ordenar descendente por timestamp (do mais novo para o mais antigo)
        valid.sort(key=lambda x: x[1], reverse=True)
        sorted_fixtures = [x[0] for x in valid]

        print(f"   ↳ {len(sorted_fixtures)} jogos concluídos a avaliar.")

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

            mid = m["match_id"]
            label = f"{m['home_name']} x {m['away_name']} ({m['kickoff_brt'].strftime('%d/%m')})"

            status = await get_match_status(pool, mid)
            if all(status.values()):
                state["last_processed_fixture_id"] = f_id
                continue

            sys.stdout.write(f"    ➜ Coletando: {label}...")
            sys.stdout.flush()

            cost = await process_match(m, status, stats_c, events_c, lineups_c, players_c, pool)
            reqs_used += cost
            print(f" OK (+{cost} req) | Total: {reqs_used}/{MAX_REQUESTS_PER_RUN}")

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
            print(f"✅ Liga {l_code} ({l_label}) inteiramente concluída.")

    print(f"\nExecução finalizada. Total requests: {reqs_used}")


if __name__ == "__main__":
    asyncio.run(run())
