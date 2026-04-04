from typing import List, Dict, Any

def parse_players(match_id: str, payload: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parsea estatísticas individuais originadas de /fixtures/players
    para a tabela match_player_stats.
    """
    records = []
    for team_data in payload:
        team_api_id = team_data.get("team", {}).get("id")
        players = team_data.get("players", [])
        
        for p in players:
            player = p.get("player", {})
            stats = p.get("statistics", [{}])[0] # O array de stat sempre tem 1 objeto para aquele jogo
            
            # Formata null -> 0 para safe insertion (quando aplicavel)
            # ou converte rating
            def safe_int(val): return int(val) if val is not None else 0
            
            rating = stats.get("games", {}).get("rating")
            rating_val = float(rating) if rating not in (None, "-", "") else None
            
            minutes = safe_int(stats.get("games", {}).get("minutes"))
            # Só armazena jogadores que pisaram no gramado (ou no mínimo estavam relacionados firmes e tem info)
            if minutes == 0:
                continue
                
            record = {
                "match_id": match_id,
                "team_api_id": team_api_id,
                "player_id": player.get("id"),
                "player_name": player.get("name"),
                "minutes_played": minutes,
                "rating": rating_val,
                
                "goals": safe_int(stats.get("goals", {}).get("total")),
                "assists": safe_int(stats.get("goals", {}).get("assists")),
                "shots_total": safe_int(stats.get("shots", {}).get("total")),
                "shots_on": safe_int(stats.get("shots", {}).get("on")),
                
                "passes_total": safe_int(stats.get("passes", {}).get("total")),
                "passes_key": safe_int(stats.get("passes", {}).get("key")),
                "passes_accuracy": float(stats.get("passes", {}).get("accuracy") or 0.0),
                
                "tackles": safe_int(stats.get("tackles", {}).get("total")),
                "blocks": safe_int(stats.get("tackles", {}).get("blocks")),
                "interceptions": safe_int(stats.get("tackles", {}).get("interceptions")),
                
                "duels_total": safe_int(stats.get("duels", {}).get("total")),
                "duels_won": safe_int(stats.get("duels", {}).get("won")),
                
                "dribbles_attempts": safe_int(stats.get("dribbles", {}).get("attempts")),
                "dribbles_success": safe_int(stats.get("dribbles", {}).get("success")),
                
                "fouls_drawn": safe_int(stats.get("fouls", {}).get("drawn")),
                "fouls_committed": safe_int(stats.get("fouls", {}).get("committed")),
                
                "cards_yellow": safe_int(stats.get("cards", {}).get("yellow")),
                "cards_red": safe_int(stats.get("cards", {}).get("red")),
                
                "offsides": safe_int(stats.get("offsides", {})), # formato as vezes difere
                "saves": safe_int(stats.get("goals", {}).get("saves"))
            }
            records.append(record)
            
    return records
