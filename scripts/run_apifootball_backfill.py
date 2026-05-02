"""
scripts/run_apifootball_backfill.py

Script de produção diário para API-Football (roda às 02:00 BRT via orchestrator).
  - Busca as ligas da temporada atual (is_current = TRUE).
  - Pula ENG_NL (sem stats no API-Football).
  - Para cada liga, puxa /fixtures da temporada e filtra os concluídos.
  - Verifica o que já existe no banco (stats/events/lineups/players).
  - Coleta apenas o que está faltando.
  - State file para retomar de onde parou entre execuções.
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
from src.alerts.telegram_mini import TelegramAlert
from src.normalizer.team_resolver import TeamResolver
from src.collectors.api_football.client import ApiFootballClient
from src.collectors.api_football.stats_collector import StatsCollector
from src.collectors.api_football.events_collector import EventsCollector
from src.collectors.api_football.lineup_collector import LineupCollector
from src.collectors.api_football.players_collector import PlayersCollector

logger = get_logger("apifb_backfill")

BRT = ZoneInfo("America/Sao_Paulo")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STATE_FILE = os.path.join(DATA_DIR, "apifootball_backfill_state.json")

MAX_REQUESTS_PER_RUN = 7300  # VIP plan: 7500/dia, margem de segurança
SKIP_LEAGUES = {"ENG_NL", "SCO_CH", "SCO_L1", "SCO_L2"}  # Ligas sem stats/events no API-Football
EARLIEST_YEAR = 2021  # Minimum season year to backfill


def load_state() -> dict:
    """Load backfill state from JSON file.
    The state now tracks the current season year being processed.
    """
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Initial state when file does not exist
    return {
        "completed_leagues": [],
        "last_processed_fixture_id": None,
        "current_year": None
    }


def save_state(state: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


async def get_active_leagues(pool) -> list:
    """Busca ligas da temporada atual com api_football_league_id configurado."""
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT l.league_id, l.code, l.api_football_league_id, CAST(LEFT(s.label, 4) AS INTEGER) AS year 
            FROM seasons s 
            JOIN leagues l ON s.league_id = l.league_id 
            WHERE CAST(LEFT(s.label, 4) AS INTEGER) >= $1 AND l.api_football_league_id IS NOT NULL
        ''', EARLIEST_YEAR)

    active_leagues = [dict(r) for r in rows]
    bra = [l for l in active_leagues if l["code"] == "BRA_SA"]
    others = [l for l in active_leagues if l["code"] != "BRA_SA"]
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


async def run_backfill(is_cron=False):
    """Run the API‑Football backfill.
    The routine now processes multiple seasons, starting from the most recent
    (current season) and descending to EARLIEST_YEAR (2021). It respects the
    daily request quota (MAX_REQUESTS_PER_RUN) and keeps state about the
    current season year and the last processed fixture.
    """
    if not is_cron:
        print("\n" + "=" * 55)
        print("      API-FOOTBALL BACKFILL — MULTI‑SEASON (2021‑ATÉ ATUAL)")
        print("=" * 55 + "\n")

    pool = await get_pool()
    await TelegramAlert.init()
    await TeamResolver.load_cache()

    leagues = await get_active_leagues(pool)
    state = load_state()
    # Initialise current_year if not present or out of range
    if state.get("current_year") is None or state.get("current_year") < EARLIEST_YEAR:
        # Determine the most recent season year among active leagues
        state["current_year"] = max(l["year"] for l in leagues)
        # Reset per-year tracking
        state["completed_leagues"] = []
        state["last_processed_fixture_id"] = None
        save_state(state)
    current_year = state["current_year"]
    completed_leagues = state.get("completed_leagues", [])
    last_fixture_id = state.get("last_processed_fixture_id")
    reqs_used = 0
    errors_found = []

    modo = "🤖 Automático (cron)" if is_cron else "🖐 Manual"
    TelegramAlert.fire(
        "info",
        f"*API-Football Backfill* iniciado\n"
        f"Modo: {modo}\n"
        f"Ligas na fila: {len(leagues)}"
    )

    stats_c = StatsCollector()
    events_c = EventsCollector()
    lineups_c = LineupCollector()
    players_c = PlayersCollector()

    # Process seasons from most recent down to EARLIEST_YEAR
    while current_year >= EARLIEST_YEAR:
        # Filter leagues for the current season year
        season_leagues = [l for l in leagues if l["year"] == current_year]
        if not season_leagues:
            # No leagues for this year, move to previous year
            current_year -= 1
            state["current_year"] = current_year
            state["completed_leagues"] = []
            state["last_processed_fixture_id"] = None
            save_state(state)
            continue

        # Use completed_leagues from state if resuming the same year;
        # only reset when advancing to a new year
        if current_year == state.get("current_year"):
            completed_leagues = state.get("completed_leagues", [])
        else:
            completed_leagues = []
            state["completed_leagues"] = completed_leagues
            state["current_year"] = current_year
            save_state(state)

        limit_reached = False
        for l_data in season_leagues:
            l_code = l_data["code"]
            l_api_id = l_data["api_football_league_id"]
            l_year = l_data["year"]
            l_db_id = l_data["league_id"]

            if l_code in SKIP_LEAGUES:
                print(f"⏭ [{l_code}] Pulando (sem stats no API-Football).")
                continue

            if l_code in completed_leagues:
                print(f"⏭ [{l_code}] ({l_year}) Já concluída nesta temporada.")
                continue

            print(f"▶ [{l_code}] ({l_year}) Puxando fixtures...")
            try:
                fixtures = await ApiFootballClient.get("/fixtures", {"league": l_api_id, "season": l_year})
                reqs_used += 1
            except Exception as e:
                msg = f"ERRO ao puxar /fixtures da {l_code} ({l_year}): {e}"
                logger.error(msg)
                print(msg)
                errors_found.append(f"[{l_code}] /fixtures: {e}")
                break

            if not fixtures:
                print("   ↳ 0 resultados.")
                continue

            # Filter completed matches
            valid = []
            for f in fixtures:
                if f["fixture"]["status"]["short"] not in ("FT", "AET", "PEN"):
                    continue
                raw_dt = datetime.fromisoformat(f["fixture"]["date"])
                valid.append((f, raw_dt.timestamp()))

            valid.sort(key=lambda x: x[1], reverse=True)
            sorted_fixtures = [x[0] for x in valid]
            print(f"   ↳ {len(sorted_fixtures)} jogos concluídos a avaliar.")

            # Fast‑forward safety check
            if last_fixture_id and not any(f["fixture"]["id"] == last_fixture_id for f in sorted_fixtures):
                print(f"    ⚠ last_fixture_id {last_fixture_id} não encontrado na lista atual. Processando sem fast‑forward.")
                last_fixture_id = None

            for f in sorted_fixtures:
                if reqs_used >= MAX_REQUESTS_PER_RUN:
                    break

                f_id = f["fixture"]["id"]

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
                print("\n[!] LIMITE ATINGIDO. Pausando execução.")
                TelegramAlert.fire(
                    "warning",
                    f"*API-Football Backfill* pausado por limite\n"
                    f"Requisições usadas: {reqs_used}/{MAX_REQUESTS_PER_RUN}\n"
                    f"Ano: {l_year} | Liga pausada: {l_code}\n"
                    f"O restante será retomado na próxima execução."
                )
                # Preserva current_year e last_processed_fixture_id para retomada exata
                state["current_year"] = current_year
                save_state(state)
                limit_reached = True
                break
            else:
                completed_leagues.append(l_code)
                state["completed_leagues"] = completed_leagues
                state["last_processed_fixture_id"] = None
                last_fixture_id = None
                save_state(state)
                print(f"✅ Liga {l_code} ({l_year}) inteiramente concluída.")

        if limit_reached:
            # Não avança o ano — próxima execução retoma de onde parou
            break

        # Temporada completa — avança para o ano anterior
        current_year -= 1
        state["current_year"] = current_year
        state["completed_leagues"] = []
        state["last_processed_fixture_id"] = None
        save_state(state)


    # All seasons processed – final cleanup
    print(f"\nExecução finalizada. Total requests: {reqs_used}")

    if errors_found:
        erros_txt = "\n".join(f"• {e}" for e in errors_found[:10])
        TelegramAlert.fire(
            "error",
            f"*API-Football Backfill* finalizado com erros\n"
            f"Requisições usadas: {reqs_used}/{MAX_REQUESTS_PER_RUN}\n"
            f"Status: ❌ Com erros\n\n"
            f"Erros encontrados:\n{erros_txt}"
        )
    else:
        status_txt = "🔄 Parcial (limite atingido)" if reqs_used >= MAX_REQUESTS_PER_RUN else "✅ Concluído sem erros"
        TelegramAlert.fire(
            "success",
            f"*API-Football Backfill* finalizado\n"
            f"Requisições usadas: {reqs_used}/{MAX_REQUESTS_PER_RUN}\n"
            f"Status: {status_txt}"
        )

    await asyncio.sleep(1)
    await TelegramAlert.close()


if __name__ == "__main__":
    asyncio.run(run_backfill(is_cron=False))
