import json
from typing import List, Dict, Any, Optional

def parse_statistics(match_id: str, payload: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parsea o payload do endpoint /fixtures/statistics.
    O endpoint retorna um array de times.
    Ex: [{"team": {"id": 126, "name": "Sao Paulo"}, "statistics": [{"type": "Shots on Goal", "value": 4}, ...]}]
    """
    records = []
    
    for team_data in payload:
        team_api_id = team_data.get("team", {}).get("id")
        if not team_api_id:
            continue
            
        stats_list = team_data.get("statistics", [])
        
        # Mapeamento do xG, Posse, Passes... para inserir em match_stats.
        # No DB atual, match_stats insere as estatisticas basicas. Se API Football
        # so atualiza o matches.xg via V_MATCH_FULL, precisamos do jsonb the estatisticas bruto se quisermos.
        # Como o schema oficial usa "source='api_football'", retornaremos de forma compativel.
        
        record = {
            "match_id": match_id,
            "team_api_id": team_api_id,
            "stats_json": json.dumps(stats_list)
        }
        records.append(record)
        
    return records
