"""
Script de validação piloto — BRA_SA 2026 
Uso: python scripts/validate_api_football_pilot.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db import helpers
from src.collectors.api_football.client import ApiFootballClient
from src.collectors.api_football.stats_collector import StatsCollector
from src.collectors.api_football.events_collector import EventsCollector
from src.collectors.api_football.lineup_collector import LineupCollector
from src.collectors.api_football.players_collector import PlayersCollector

async def validate_results(date_str: str):
    print(f"\n--- Validação do Banco de Dados Pós-Coleta (Data: {date_str}) ---")
    q_matches = """
        SELECT COUNT(*) FROM matches 
        WHERE kickoff::date = $1 
          AND league_id = (SELECT league_id FROM leagues WHERE code = 'BRA_SA')
          AND api_football_id IS NOT NULL
    """
    
    from datetime import date
    target_date = date.fromisoformat(date_str)
    
    val_matches = await helpers.fetch_val(q_matches, target_date)
    print(f"Partidas mapeadas no dia: {val_matches}")
    
    val_stats = await helpers.fetch_val("SELECT COUNT(*) FROM match_stats WHERE source = 'api_football'")
    print(f"Total entries match_stats: {val_stats}")
    
    val_events = await helpers.fetch_val("SELECT COUNT(*) FROM match_events")
    print(f"Total entries match_events: {val_events}")
    
    val_lineups = await helpers.fetch_val("SELECT COUNT(*) FROM lineups WHERE source = 'api_football'")
    print(f"Total entries lineups: {val_lineups}")
    
    val_players = await helpers.fetch_val("SELECT COUNT(*) FROM match_player_stats")
    print(f"Total entries match_player_stats: {val_players}")

async def main():
    date_str = "2026-04-01"
    
    print("Iniciando Validação Piloto API-Football.")
    print(f"League: BRA_SA (71) | Season: 2026 | Date: {date_str}")
    
    # Bypass the database active .env keys to use the one explicitly allowed for 2026
    # No ambiente de produção o KeyManager pegará a chave normal
    import httpx
    ApiFootballClient.BASE_URL = "https://v3.football.api-sports.io"
    
    original_get = ApiFootballClient.get
    
    @classmethod
    async def mockup_get(cls, endpoint: str, params: dict = None):
        await cls._wait_for_rate_limit()
        headers = {"x-apisports-key": "11b0151f3fcf9b5522de91b35f6b556b"}
        url = f"{cls.BASE_URL}{endpoint}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            return resp.json().get("response", [])
            
    # Mock para usar a key correta nos collectors
    ApiFootballClient.get = mockup_get
    
    pool = await get_pool()
    
    from datetime import date
    target_date = date.fromisoformat(date_str)
    
    # 1. Obter matches com api_football_id para a data
    async with pool.acquire() as conn:
        db_matches = await conn.fetch(
            """
            SELECT m.match_id, m.api_football_id, m.home_team_id, m.away_team_id
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.kickoff::date = $1 AND l.api_football_league_id = 71
            """, target_date
        )
        
    if not db_matches:
        print(f"Atenção: Não há partidas em v_today_matches_apifb para {date_str}")
        print("Buscando /fixtures na API para atrelar os IDs...")
        fixtures = await ApiFootballClient.get("/fixtures", {"date": date_str, "league": 71, "season": 2026})
        
        # Faz mapping basico pegando os times no db (match mais rapido assumindo consistencia de horarios)
        # O MatchResolver seria usado aqui em producao, mas para o piloto atrelaremos o primeiro match
        if fixtures:
            print(f"Fixtures API encontradas: {len(fixtures)}.")
            for f in fixtures:
                af_id = f["fixture"]["id"]
                h_name = f["teams"]["home"]["name"]
                a_name = f["teams"]["away"]["name"]
                print(f"Descoberta: {af_id} -> {h_name} x {a_name}")
                
            print("Por favor, garanta que suas tabelas de alias atrelaram essas partidas na tabela matches e de um UPDATE matches SET api_football_id = ...")
            print("Para esta validação isolada, estou buscando *apenas* a fixture e não mapeando contra o banco sem MatchResolver.")
            
            # Pra gente rodar os collectors, a gente pode puxar um db_matches list falso 
            # ou usar team id do banco reais se sabermos, senao os collectors vao falhar a Constraint de foreign key!
            db_matches = []
            async with pool.acquire() as conn:
                matches_exist = await conn.fetch("SELECT match_id, home_team_id, away_team_id FROM matches WHERE kickoff::date = $1 AND league_id = (SELECT league_id FROM leagues WHERE code = 'BRA_SA')", target_date)
                if matches_exist:
                    # Fake map just to test DB Insertions (assuming order is the same)
                    print(f"Forçando mapeamento temporário de IDs para os {len(matches_exist)} matches do dia {date_str}...")
                    for i, mx in enumerate(matches_exist):
                        if i < len(fixtures):
                            db_matches.append({
                                "match_id": mx["match_id"],
                                "api_football_id": fixtures[i]["fixture"]["id"],
                                "home_team_id": mx["home_team_id"],
                                "away_team_id": mx["away_team_id"],
                                "home_api_id": fixtures[i]["teams"]["home"]["id"],
                                "away_api_id": fixtures[i]["teams"]["away"]["id"],
                            })
        else:
            print("Nenhum jogo retornado da API.")
            return
            
    stats_c = StatsCollector()
    events_c = EventsCollector()
    lineups_c = LineupCollector()
    players_c = PlayersCollector()
    
    for match in db_matches:
        mid = str(match["match_id"])
        fid = match["api_football_id"]
        
        team_map = {
            match["home_api_id"]: match["home_team_id"],
            match["away_api_id"]: match["away_team_id"]
        }
        
        print(f"\nIniciando Coleta Fixture {fid} (Match ID: {mid})")
        r_stats = await stats_c.collect(mid, fid, team_map)
        print(f" └─ Stats:   Inclusos {r_stats.records_new}")
        
        r_events = await events_c.collect(mid, fid, team_map)
        print(f" └─ Events:  Inclusos {r_events.records_new}")
        
        r_lineup = await lineups_c.collect(mid, fid, team_map)
        print(f" └─ Lineup:  Inclusos {r_lineup.records_new}")
        
        r_players = await players_c.collect(mid, fid, team_map)
        print(f" └─ Players: Inclusos {r_players.records_new}")

    await validate_results(date_str)

if __name__ == "__main__":
    asyncio.run(main())
