import json
from typing import List, Dict, Any

def parse_lineups(match_id: str, payload: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parsea o payload de /fixtures/lineups para a nova estrutura de `lineups`.
    O array payload possui os dados para team home [0] e away [1].
    """
    records = []
    
    for i, team_data in enumerate(payload):
        team_api_id = team_data.get("team", {}).get("id")
        if not team_api_id:
            continue
            
        formation = team_data.get("formation")
        is_home = (i == 0) # API-Football sempre retorna Home depois Away
        
        # Consolida jogadores titular e reserva num dicionário para players_json
        players_json = {
            "coach": team_data.get("coach", {}),
            "startXI": [p.get("player") for p in team_data.get("startXI", [])],
            "substitutes": [p.get("player") for p in team_data.get("substitutes", [])]
        }
        
        record = {
            "match_id": match_id,
            "team_api_id": team_api_id,
            "is_home": is_home,
            "formation": formation,
            "players_json": json.dumps(players_json),
            "source": "api_football"
        }
        records.append(record)
        
    return records
