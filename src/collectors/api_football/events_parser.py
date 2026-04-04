from typing import List, Dict, Any

def parse_events(match_id: str, payload: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parsea os eventos de uma fixture. Foca em 'Goal' e 'Card'.
    """
    records = []
    for event in payload:
        event_time = event.get("time", {})
        team = event.get("team", {})
        player = event.get("player", {})
        assist = event.get("assist", {})
        
        record = {
            "match_id": match_id,
            "time_elapsed": event_time.get("elapsed"),
            "time_extra": event_time.get("extra"),
            "team_api_id": team.get("id"),
            "player_id": player.get("id"),
            "player_name": player.get("name"),
            "assist_id": assist.get("id"),
            "assist_name": assist.get("name"),
            "event_type": event.get("type"), # 'Goal', 'Card', 'subst', 'Var'
            "event_detail": event.get("detail"), # 'Yellow Card', 'Normal Goal', 'Penalty'
            "comments": event.get("comments")
        }
        
        # Ignorar eventos vazios sem tempo
        if record["time_elapsed"] is not None:
            records.append(record)
            
    return records
