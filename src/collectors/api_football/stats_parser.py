import json
from typing import List, Dict, Any

def parse_statistics(match_id: str, payload: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parsea o payload do endpoint /fixtures/statistics (API-Football).
    Mapeia propriedades específicas em chaves terminadas em _home ou _away.
    """
    result = {"match_id": match_id}
    
    # helper para converter percentuais "69%" em float
    def parse_val(v):
        if v is None:
            return None
        if isinstance(v, str):
            v_clean = v.replace("%", "").strip()
            try:
                # Tenta converter para int ou float
                if "." in v_clean:
                    return float(v_clean)
                return int(v_clean)
            except ValueError:
                return v
        return v
    
    # A API sempre retorna [HOME, AWAY] nesta ordem.
    for i, team_data in enumerate(payload):
        suffix = "_home" if i == 0 else "_away"
        stats_list = team_data.get("statistics", [])
        
        for stat in stats_list:
            t = stat.get("type")
            v = stat.get("value")
            
            p_val = parse_val(v)
            
            if t == "Shots off Goal": result[f"shots_off_goal{suffix}"] = p_val
            elif t == "Blocked Shots": result[f"blocked_shots{suffix}"] = p_val
            elif t == "Shots insidebox": result[f"shots_insidebox{suffix}"] = p_val
            elif t == "Shots outsidebox": result[f"shots_outsidebox{suffix}"] = p_val
            elif t == "Goalkeeper Saves": result[f"goalkeeper_saves{suffix}"] = p_val
            elif t == "Total passes": result[f"total_passes{suffix}"] = p_val
            elif t == "Passes accurate": result[f"passes_accurate{suffix}"] = p_val
            elif t == "Passes %": result[f"passes_pct{suffix}"] = p_val
            elif t == "expected_goals": result[f"expected_goals{suffix}"] = p_val

    return result

