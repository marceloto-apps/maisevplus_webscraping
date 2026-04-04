"""
validate_api_football_pilot.py
================================
Валидação piloto do pipeline API-Football para BRA_SA 2026.

Fluxo:
  1. Carrega api_football_sample.json (sem gastar cota)
  2. Filtra jogos de TARGET_DATE
  3. Resolve fixture → match_id via MatchResolver + team aliases
  4. Chama stats / events / lineups / players via API (4 req × N jogos)
  5. Exibe contagem de registros inseridos

Uso:
    python scripts/validate_api_football_pilot.py
    python scripts/validate_api_football_pilot.py --date 2026-04-01
"""

import asyncio
import json
import os
import sys
import argparse
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db import helpers
from src.normalizer.team_resolver import TeamResolver, MatchResolver
from src.collectors.api_football.client import ApiFootballClient
from src.collectors.api_football.stats_collector import StatsCollector
from src.collectors.api_football.events_collector import EventsCollector
from src.collectors.api_football.lineup_collector import LineupCollector
from src.collectors.api_football.players_collector import PlayersCollector

SAMPLE_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "api_football_sample.json"
)

# ID da liga BRA_SA na API-Football
LEAGUE_API_ID = 71


async def load_fixtures_for_date(target_date: date) -> list:
    """Carrega fixtures do JSON local e filtra pela data alvo."""
    with open(SAMPLE_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # O JSON pode ser a resposta completa {response: [...]} ou lista direta
    if isinstance(raw, dict) and "response" in raw:
        all_fixtures = raw["response"]
    elif isinstance(raw, list):
        all_fixtures = raw
    else:
        # Tenta pegar o primeiro valor do dict que seja lista
        for v in raw.values():
            if isinstance(v, list):
                all_fixtures = v
                break
        else:
            all_fixtures = []

    filtered = [
        f for f in all_fixtures
        if f.get("fixture", {}).get("date", "")[:10] == target_date.isoformat()
    ]
    return filtered


async def resolve_fixture_to_match(pool, fixture: dict, league_id: int) -> dict | None:
    """
    Resolve um fixture da API-Football para um match_id no banco.
    Usa TeamResolver para mapear os nomes dos times.
    """
    home_name = fixture["teams"]["home"]["name"]
    away_name = fixture["teams"]["away"]["name"]
    af_fixture_id = fixture["fixture"]["id"]
    kickoff_str = fixture["fixture"]["date"][:10]
    kickoff_date = date.fromisoformat(kickoff_str)

    home_api_id = fixture["teams"]["home"]["id"]
    away_api_id = fixture["teams"]["away"]["id"]

    # Tentativa 1: resolver pelo api_football_id dos times
    async with pool.acquire() as conn:
        home_db_id = await conn.fetchval(
            "SELECT team_id FROM teams WHERE api_football_id = $1", home_api_id
        )
        away_db_id = await conn.fetchval(
            "SELECT team_id FROM teams WHERE api_football_id = $1", away_api_id
        )

    # Tentativa 2: fallback via alias
    if home_db_id is None:
        home_db_id = await TeamResolver.resolve("api_football", home_name)
    if away_db_id is None:
        away_db_id = await TeamResolver.resolve("api_football", away_name)

    if home_db_id is None or away_db_id is None:
        print(f"  ⚠ Não resolvido: {home_name} x {away_name} (api_football_id: home={home_api_id} away={away_api_id})")
        return None

    # Resolver match_id no banco
    match_id = await MatchResolver.resolve_with_footystats(
        league_id, home_name, away_name, kickoff_date, footystats_id=None
    )

    if match_id is None:
        # Fallback: busca direta por time + data
        async with pool.acquire() as conn:
            match_id = await conn.fetchval(
                """
                SELECT match_id FROM matches
                WHERE home_team_id = $1
                  AND away_team_id = $2
                  AND kickoff::date = $3
                  AND league_id = $4
                LIMIT 1
                """,
                home_db_id, away_db_id, kickoff_date, league_id
            )

    if match_id is None:
        print(f"  ⚠ Match não encontrado no banco: {home_name} x {away_name} em {kickoff_date}")
        return None

    # Atualiza api_football_id no match se ainda não tiver
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE matches SET api_football_id = $1 WHERE match_id = $2 AND api_football_id IS NULL",
            str(af_fixture_id), match_id
        )

    return {
        "match_id": match_id,
        "api_football_id": af_fixture_id,
        "home_team_id": home_db_id,
        "away_team_id": away_db_id,
        "home_api_id": home_api_id,
        "away_api_id": away_api_id,
        "home_name": home_name,
        "away_name": away_name,
    }


async def validate_results(target_date: date):
    print(f"\n{'='*55}")
    print(f"  Validação do banco — {target_date}")
    print(f"{'='*55}")

    stats = await helpers.fetch_val(
        "SELECT COUNT(*) FROM match_stats WHERE source = 'api_football'"
    )
    events = await helpers.fetch_val("SELECT COUNT(*) FROM match_events")
    lineups = await helpers.fetch_val(
        "SELECT COUNT(*) FROM lineups WHERE source = 'api_football'"
    )
    players = await helpers.fetch_val("SELECT COUNT(*) FROM match_player_stats")

    print(f"  match_stats    (api_football): {stats}")
    print(f"  match_events               : {events}")
    print(f"  lineups        (api_football): {lineups}")
    print(f"  match_player_stats         : {players}")
    print()


async def main(target_date: date):
    print(f"\n{'='*55}")
    print(f"  API-Football Pilot Validator")
    print(f"  BRA_SA 2026 | Data: {target_date}")
    print(f"{'='*55}\n")

    pool = await get_pool()
    await TeamResolver.load_cache()

    # Liga BRA_SA no banco
    async with pool.acquire() as conn:
        league_id = await conn.fetchval(
            "SELECT league_id FROM leagues WHERE code = 'BRA_SA'"
        )

    if not league_id:
        print("ERRO: BRA_SA não encontrada no banco.")
        return

    # Carregar fixtures do JSON
    fixtures = await load_fixtures_for_date(target_date)
    if not fixtures:
        print(f"Nenhum fixture encontrado no JSON para {target_date}")
        print(f"Arquivo: {SAMPLE_JSON}")
        return

    print(f"✓ {len(fixtures)} fixture(s) encontrada(s) em {target_date} no JSON\n")

    # Resolver cada fixture para match_id no banco
    resolved = []
    for f in fixtures:
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        print(f"  Resolvendo: {home} x {away}...", end=" ")
        m = await resolve_fixture_to_match(pool, f, league_id)
        if m:
            print(f"✓ match_id={m['match_id']}")
            resolved.append(m)
        else:
            print("✗ não resolvido")

    if not resolved:
        print("\nNenhum match resolvido. Verifique os mapeamentos de times (api_football_id).")
        return

    print(f"\n✓ {len(resolved)}/{len(fixtures)} fixture(s) resolvida(s). Iniciando coleta de detalhes...\n")

    # Collectors
    stats_c = StatsCollector()
    events_c = EventsCollector()
    lineups_c = LineupCollector()
    players_c = PlayersCollector()

    total_stats = total_events = total_lineups = total_players = 0

    for m in resolved:
        mid = str(m["match_id"])
        fid = m["api_football_id"]
        team_map = {
            m["home_api_id"]: m["home_team_id"],
            m["away_api_id"]: m["away_team_id"],
        }

        label = f"{m['home_name']} x {m['away_name']}"
        print(f"  [{fid}] {label}")

        try:
            r_stats = await stats_c.collect(mid, fid, team_map)
            print(f"    Stats:   {r_stats.records_new} novos")
            total_stats += r_stats.records_new
        except Exception as e:
            print(f"    Stats:   ERRO — {e}")

        try:
            r_events = await events_c.collect(mid, fid, team_map)
            print(f"    Events:  {r_events.records_new} novos")
            total_events += r_events.records_new
        except Exception as e:
            print(f"    Events:  ERRO — {e}")

        try:
            r_lineup = await lineups_c.collect(mid, fid, team_map)
            print(f"    Lineup:  {r_lineup.records_new} novos")
            total_lineups += r_lineup.records_new
        except Exception as e:
            print(f"    Lineup:  ERRO — {e}")

        try:
            r_players = await players_c.collect(mid, fid, team_map)
            print(f"    Players: {r_players.records_new} novos")
            total_players += r_players.records_new
        except Exception as e:
            print(f"    Players: ERRO — {e}")

        print()

    print(f"{'='*55}")
    print(f"  Totais inseridos")
    print(f"  Stats:   {total_stats}")
    print(f"  Events:  {total_events}")
    print(f"  Lineups: {total_lineups}")
    print(f"  Players: {total_players}")

    await validate_results(target_date)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-04-01", help="Data no formato YYYY-MM-DD")
    args = parser.parse_args()
    asyncio.run(main(date.fromisoformat(args.date)))
