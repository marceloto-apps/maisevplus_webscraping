"""
validate_api_football_pilot.py
================================
Validação do pipeline API-Football usando dados locais do arquivo JSON.
NÃO faz nenhuma chamada à API.

Fluxo:
  1. Carrega api_football_sample.json (fixture: Internacional x São Paulo, 01/04/2026)
  2. Mapeia os times via api_football_id na tabela teams
  3. Resolve o match_id no banco (BRA_SA league)
  4. Chama os parsers com os dados do JSON
  5. Insere em match_events, lineups, match_player_stats
  6. Exibe contagem de registros

Uso:
    python scripts/validate_api_football_pilot.py
"""

import asyncio
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db.logger import get_logger
from src.collectors.api_football.events_parser import parse_events
from src.collectors.api_football.lineup_parser import parse_lineups
from src.collectors.api_football.players_parser import parse_players

logger = get_logger(__name__)

SAMPLE_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "api_football_sample.json"
)


async def main():
    print("\n" + "="*55)
    print("  API-Football Pilot Validator (offline — JSON local)")
    print("="*55 + "\n")

    # ── 1. Carregar JSON ──────────────────────────────────────
    with open(SAMPLE_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)

    fi          = raw["fixture_info"]
    fixture_id  = fi["fixture"]["id"]
    kickoff_str = fi["fixture"]["date"][:10]
    kickoff_d   = date.fromisoformat(kickoff_str)
    home_name   = fi["teams"]["home"]["name"]
    away_name   = fi["teams"]["away"]["name"]
    home_api_id = fi["teams"]["home"]["id"]
    away_api_id = fi["teams"]["away"]["id"]
    score       = fi["score"]["fulltime"]

    print(f"  Fixture : {fixture_id}")
    print(f"  Jogo    : {home_name} {score['home']} x {score['away']} {away_name}")
    print(f"  Data    : {kickoff_str}")
    print(f"  Eventos : {len(raw['events'])}")
    print(f"  Lineups : {len(raw['lineups'])} times")
    print(f"  Players : {sum(len(p.get('players',[])) for p in raw['players'])} jogadores\n")

    pool = await get_pool()

    # ── 2. Mapear api_football_id → team_id no banco ─────────
    async with pool.acquire() as conn:
        home_db_id = await conn.fetchval(
            "SELECT team_id FROM teams WHERE api_football_id = $1", home_api_id
        )
        away_db_id = await conn.fetchval(
            "SELECT team_id FROM teams WHERE api_football_id = $1", away_api_id
        )
        league_id = await conn.fetchval(
            "SELECT league_id FROM leagues WHERE code = 'BRA_SA'"
        )

    if not home_db_id or not away_db_id:
        print(f"  ⚠ Times não mapeados via api_football_id:")
        print(f"    Home: {home_name} (api_id={home_api_id}) → db_id={home_db_id}")
        print(f"    Away: {away_name} (api_id={away_api_id}) → db_id={away_db_id}")
        print("\n  Execute o script de mapeamento ou insira manualmente na coluna api_football_id da tabela teams.")
        return

    print(f"  ✓ Times mapeados:")
    print(f"    {home_name} → db_id {home_db_id}")
    print(f"    {away_name} → db_id {away_db_id}\n")

    team_map = {home_api_id: home_db_id, away_api_id: away_db_id}

    # ── 3. Resolver match_id no banco ─────────────────────────
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
            home_db_id, away_db_id, kickoff_d, league_id
        )

    if not match_id:
        print(f"  ⚠ Match não encontrado no banco para {home_name} x {away_name} em {kickoff_d}.")
        print("    Verifique se o daily_updater já processou o BRA_SA para esta data.")
        return

    print(f"  ✓ match_id = {match_id}\n")

    # Atualiza api_football_id no match
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE matches SET api_football_id = $1 WHERE match_id = $2",
            str(fixture_id), match_id
        )
    print(f"  ✓ api_football_id={fixture_id} salvo no match\n")

    mid = str(match_id)

    # ── 4. Inserir EVENTOS ────────────────────────────────────
    events_parsed = parse_events(mid, raw["events"])
    ev_ok = ev_skip = 0
    async with pool.acquire() as conn:
        for ev in events_parsed:
            db_team = team_map.get(ev["team_api_id"])
            if not db_team:
                ev_skip += 1
                continue
            await conn.execute(
                """
                INSERT INTO match_events (
                    match_id, time_elapsed, time_extra, team_id,
                    player_id, player_name, assist_id, assist_name,
                    event_type, event_detail, comments
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (match_id, team_id, time_elapsed, time_extra, event_type, player_name)
                DO NOTHING
                """,
                match_id,
                ev["time_elapsed"], ev["time_extra"], db_team,
                ev["player_id"], ev["player_name"],
                ev["assist_id"], ev["assist_name"],
                ev["event_type"], ev["event_detail"], ev["comments"]
            )
            ev_ok += 1

    print(f"  ✓ Events  : {ev_ok} inseridos | {ev_skip} sem team_map")

    # ── 5. Inserir LINEUPS ────────────────────────────────────
    lineups_parsed = parse_lineups(mid, raw["lineups"])
    ln_ok = ln_skip = 0
    async with pool.acquire() as conn:
        for ln in lineups_parsed:
            db_team = team_map.get(ln["team_api_id"])
            if not db_team:
                ln_skip += 1
                continue
            await conn.execute(
                """
                INSERT INTO lineups (match_id, team_id, formation, players_json, is_home, source)
                VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                ON CONFLICT (match_id, team_id, source)
                DO UPDATE SET formation=EXCLUDED.formation, players_json=EXCLUDED.players_json
                """,
                match_id, db_team,
                ln["formation"], ln["players_json"], ln["is_home"], "api_football"
            )
            ln_ok += 1

    print(f"  ✓ Lineups : {ln_ok} inseridos | {ln_skip} sem team_map")

    # ── 6. Inserir PLAYER STATS ───────────────────────────────
    players_parsed = parse_players(mid, raw["players"])
    pl_ok = pl_skip = 0
    async with pool.acquire() as conn:
        for pl in players_parsed:
            db_team = team_map.get(pl["team_api_id"])
            if not db_team:
                pl_skip += 1
                continue
            await conn.execute(
                """
                INSERT INTO match_player_stats (
                    match_id, team_id, player_id, player_name, minutes_played, rating,
                    goals, assists, shots_total, shots_on,
                    passes_total, passes_key, passes_accuracy,
                    tackles, blocks, interceptions,
                    duels_total, duels_won,
                    dribbles_attempts, dribbles_success,
                    fouls_drawn, fouls_committed,
                    cards_yellow, cards_red, offsides, saves
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,
                    $7,$8,$9,$10,
                    $11,$12,$13,
                    $14,$15,$16,
                    $17,$18,
                    $19,$20,
                    $21,$22,
                    $23,$24,$25,$26
                )
                ON CONFLICT (match_id, player_id)
                DO UPDATE SET
                    minutes_played=EXCLUDED.minutes_played, rating=EXCLUDED.rating,
                    goals=EXCLUDED.goals, assists=EXCLUDED.assists
                """,
                match_id, db_team, pl["player_id"], pl["player_name"],
                pl["minutes_played"], pl["rating"],
                pl["goals"], pl["assists"], pl["shots_total"], pl["shots_on"],
                pl["passes_total"], pl["passes_key"], pl["passes_accuracy"],
                pl["tackles"], pl["blocks"], pl["interceptions"],
                pl["duels_total"], pl["duels_won"],
                pl["dribbles_attempts"], pl["dribbles_success"],
                pl["fouls_drawn"], pl["fouls_committed"],
                pl["cards_yellow"], pl["cards_red"], pl["offsides"], pl["saves"]
            )
            pl_ok += 1

    print(f"  ✓ Players : {pl_ok} inseridos | {pl_skip} sem team_map")

    # ── 7. Validação final no banco ───────────────────────────
    print("\n" + "─"*55)
    print("  Contagem no banco pós-inserção:")
    async with pool.acquire() as conn:
        ev_count  = await conn.fetchval("SELECT COUNT(*) FROM match_events WHERE match_id=$1", match_id)
        ln_count  = await conn.fetchval("SELECT COUNT(*) FROM lineups WHERE match_id=$1 AND source='api_football'", match_id)
        pl_count  = await conn.fetchval("SELECT COUNT(*) FROM match_player_stats WHERE match_id=$1", match_id)
    print(f"    match_events        : {ev_count}")
    print(f"    lineups (api_fb)    : {ln_count}")
    print(f"    match_player_stats  : {pl_count}")
    print()

    if ev_count >= len(events_parsed) - ev_skip \
            and ln_count == len(lineups_parsed) - ln_skip \
            and pl_count >= len(players_parsed) - pl_skip:
        print("  ✅ Pipeline OK — todos os dados inseridos corretamente!")
    else:
        print("  ⚠  Contagem divergente — verificar logs acima.")

    print("="*55 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
