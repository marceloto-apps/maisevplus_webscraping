"""
scripts/run_apifootball_backfill.py

Script para backfill inteligente da API-Football.
  - Prioriza a liga BRA_SA; depois demais ligas ativas em ordem alfabética.
  - Começa na data alvo (03/04/2026 por padrão) e vai percorrendo dia a dia até hoje.
  - Mantém o estado no arquivo `data/apifootball_backfill_state.json` para retomar de onde parou.
  - Conta requisições localmente (1 para /fixtures, 4 para os data collectors da partida).
  - Interrompe a execução elegantemente ao chegar na margem segura (ex: ~650 requisições).
  
Uso:
  python scripts/run_apifootball_backfill.py
"""

import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db.logger import get_logger
from src.normalizer.team_resolver import TeamResolver, MatchResolver
from src.collectors.api_football.client import ApiFootballClient
from src.collectors.api_football.stats_collector import StatsCollector
from src.collectors.api_football.events_collector import EventsCollector
from src.collectors.api_football.lineup_collector import LineupCollector
from src.collectors.api_football.players_collector import PlayersCollector

logger = get_logger(__name__)

BRT = ZoneInfo("America/Sao_Paulo")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STATE_FILE = os.path.join(DATA_DIR, "apifootball_backfill_state.json")

# Limite de requests que o script executará antes de pausar
MAX_REQUESTS_PER_RUN = 650

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "current_league": "BRA_SA",
        "current_date": "2026-04-03",
        "completed_leagues": []
    }

def save_state(state: dict):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

async def get_active_leagues(pool) -> list:
    """Busca todas as ligas correntes (is_current=TRUE) que possuem ID da API-Football."""
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT l.league_id, l.code, l.api_football_league_id, s.year 
            FROM seasons s 
            JOIN leagues l ON s.league_id = l.league_id 
            WHERE s.is_current = TRUE AND l.api_football_league_id IS NOT NULL
        ''')
    
    # Ordenar: BRA_SA como primeira; as demais ordenadas por code
    active_leagues = [dict(r) for r in rows]
    # Separa o Brasil
    bra = [l for l in active_leagues if l["code"] == "BRA_SA"]
    others = [l for l in active_leagues if l["code"] != "BRA_SA"]
    others.sort(key=lambda x: x["code"])
    
    return bra + others

async def process_match(m: dict, stats_c, events_c, lineups_c, players_c, pool) -> int:
    """Processa um dicionário resolved match. Retorna o número de reqs efetuadas (deve ser 4)."""
    mid = str(m["match_id"])
    fid = m["api_football_id"]
    team_map = {
        m["home_api_id"]: m["home_team_id"],
        m["away_api_id"]: m["away_team_id"],
    }
    
    req_count = 0
    
    # Evita duplicação no output, apenas executa
    try:
        r_stats = await stats_c.collect(mid, fid, team_map)
        req_count += 1
    except Exception as e:
        logger.error(f"backfill_stats_err", match_id=mid, error=str(e))
        
    try:
        r_events = await events_c.collect(mid, fid, team_map)
        req_count += 1
    except Exception as e:
        logger.error(f"backfill_events_err", match_id=mid, error=str(e))
        
    try:
        r_lineups = await lineups_c.collect(mid, fid, team_map)
        req_count += 1
    except Exception as e:
        logger.error(f"backfill_lineups_err", match_id=mid, error=str(e))
        
    try:
        r_players = await players_c.collect(mid, fid, team_map)
        req_count += 1
    except Exception as e:
        logger.error(f"backfill_players_err", match_id=mid, error=str(e))
        
    # Salvar ID na tabela matches (para garantir) - ja estava salvo mas bom reforçar
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE matches SET api_football_id = $1 WHERE match_id = $2",
            fid, m["match_id"]
        )

    return req_count

async def resolve_fixture_to_match(pool, fixture: dict, league_id: int) -> dict | None:
    """Resolve um fixture da API-Football para um match_id no banco."""
    # Extrai o timezone para BRT para identificar a data local correta
    fi_date_str = fixture["fixture"]["date"]
    raw_dt = datetime.fromisoformat(fi_date_str)
    kickoff_brt = raw_dt.astimezone(BRT)
    kickoff_d = kickoff_brt.date()
    
    home_name = fixture["teams"]["home"]["name"]
    away_name = fixture["teams"]["away"]["name"]
    af_fixture_id = fixture["fixture"]["id"]

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
        print(f"    \u26a0 N\u00e3o resolvido times: {home_name} ({home_db_id}) x {away_name} ({away_db_id})")
        return None

    # Resolver match_id no banco -> janela de +- 1 dia para tratar fuso
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
        print(f"    \u26a0 Match não encontrado no DB para db_teams {home_db_id} x {away_db_id} perto de {kickoff_d}.")
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
    }


async def main():
    print("\n" + "="*55)
    print("      API-FOOTBALL BACKFILL (Cotas Livres)")
    print("="*55 + "\n")
    
    pool = await get_pool()
    await TeamResolver.load_cache()
    
    leagues = await get_active_leagues(pool)
    if not leagues:
        print("Nenhuma liga ativa com api_football_league_id mapeada.")
        return
        
    state = load_state()
    active_league_code = state.get("current_league", "BRA_SA")
    active_date = date.fromisoformat(state.get("current_date", "2026-04-03"))
    completed_leagues = state.get("completed_leagues", [])
    
    reqs_used_this_run = 0
    today_brt = datetime.now(BRT).date()
    
    stats_c = StatsCollector()
    events_c = EventsCollector()
    lineups_c = LineupCollector()
    players_c = PlayersCollector()

    for l_data in leagues:
        l_code = l_data["code"]
        l_api_id = l_data["api_football_league_id"]
        l_year = l_data["year"]
        l_db_id = l_data["league_id"]
        
        # Pula as que já terminaram o backfill integralmente
        if l_code in completed_leagues:
            continue
            
        # Pula até chegar na liga que estávamos (caso a gente reinicie a execução)
        if l_code != active_league_code and active_league_code not in completed_leagues:
            # So vamos rodar a liga se for a 'current_league' registrada,
            # OU se a 'current_league' já foi pra completed_leagues
            continue

        print(f"▶ Iniciando backfill: {l_code} (API_ID: {l_api_id}) | Ano: {l_year}")
        
        # Pega de onde paramos na liga (e so pega a ativa caso seja a active_league, senão recomeça do dia 3)
        if l_code == active_league_code:
            curr_date = active_date
        else:
            curr_date = date(2026, 4, 3) # default caso mude de liga

        while curr_date <= today_brt:
            if reqs_used_this_run >= MAX_REQUESTS_PER_RUN:
                print(f"\n[!] LIMITE ATINGIDO ({reqs_used_this_run}/{MAX_REQUESTS_PER_RUN}). Salvando estado e pausando.")
                state["current_league"] = l_code
                state["current_date"] = curr_date.isoformat()
                state["completed_leagues"] = completed_leagues
                save_state(state)
                return
            
            date_str = curr_date.isoformat()
            
            print(f"  [{date_str}] Buscando fixtures na API...", end=" ")
            try:
                fixtures = await ApiFootballClient.get("/fixtures", {"date": date_str, "league": l_api_id, "season": l_year})
                reqs_used_this_run += 1
            except Exception as e:
                # Tratar erro de quota ou rate limit abortando p/ salvar estado
                print(f"ERRO: {e}")
                if "Quota" in str(e) or "rate" in str(e).lower():
                    print("\n[!] QUOTA ou ERRO estrito. Salvando estado e pausando.")
                    state["current_league"] = l_code
                    state["current_date"] = curr_date.isoformat()
                    state["completed_leagues"] = completed_leagues
                    save_state(state)
                    return
                fixtures = []
            
            if fixtures:
                # Filtrar matches ja finalizados
                finished_fixtures = [f for f in fixtures if f["fixture"]["status"]["short"] in ("FT", "AET", "PEN")]
                print(f"{len(finished_fixtures)} terminados.")
                
                for f in finished_fixtures:
                    m = await resolve_fixture_to_match(pool, f, l_db_id)
                    if m:
                        sys.stdout.write(f"    ➜ Processando match {m['match_id'][:8]} ({m['home_name']} x {m['away_name']})... ")
                        sys.stdout.flush()
                        
                        cost = await process_match(m, stats_c, events_c, lineups_c, players_c, pool)
                        reqs_used_this_run += cost
                        print(f"OK (+{cost} reqs)")
                        
                        if reqs_used_this_run >= MAX_REQUESTS_PER_RUN:
                            break # corta e cai na verificacao do L235 pro loop while
            else:
                print("0 partidas.")
                
            curr_date += timedelta(days=1)
            
        # Ao sair do while, se for porque passou de last_date
        if curr_date > today_brt:
            print(f"✅ Liga {l_code} concluída até hoje. Adicionando aos completados.")
            completed_leagues.append(l_code)
            
            state["completed_leagues"] = completed_leagues
            save_state(state)

    print("\n" + "="*55)
    print("🎉 BACKFILL CONCLUÍDO PARA TODAS AS LIGAS ATIVAS!")
    print("="*55 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
