import json
from typing import List, Dict, Any


def parse_lineups(match_id: str, payload: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parsea o payload de /fixtures/lineups para linhas individuais por jogador/técnico.

    Retorna uma lista de dicts onde cada item representa um jogador ou o técnico,
    com as chaves:
        match_id, team_api_id, is_home, formation,
        fixture_position, player_id, player_name,
        player_number, player_pos, player_grid, source

    fixture_position pode ser: 'coach' | 'startXI' | 'substitutes'

    Para o técnico:
        player_pos  = 'coach'
        player_number = None
        player_grid   = None

    Para substitutos:
        player_grid = None (API não retorna grid para reservas)
    """
    records = []

    for i, team_data in enumerate(payload):
        team_api_id = team_data.get("team", {}).get("id")
        if not team_api_id:
            continue

        formation = team_data.get("formation")
        is_home = (i == 0)  # API-Football sempre retorna Home[0] Away[1]

        # ── Técnico ───────────────────────────────────────────────
        coach = team_data.get("coach", {})
        records.append({
            "match_id":         match_id,
            "team_api_id":      team_api_id,
            "is_home":          is_home,
            "formation":        formation,
            "fixture_position": "coach",
            "player_id":        coach.get("id"),
            "player_name":      coach.get("name"),
            "player_number":    None,
            "player_pos":       "coach",
            "player_grid":      None,
            "source":           "api_football",
        })

        # ── Titulares (startXI) ───────────────────────────────────
        for entry in team_data.get("startXI", []):
            p = entry.get("player", {})
            records.append({
                "match_id":         match_id,
                "team_api_id":      team_api_id,
                "is_home":          is_home,
                "formation":        formation,
                "fixture_position": "startXI",
                "player_id":        p.get("id"),
                "player_name":      p.get("name"),
                "player_number":    p.get("number"),
                "player_pos":       p.get("pos"),
                "player_grid":      p.get("grid"),
                "source":           "api_football",
            })

        # ── Reservas (substitutes) ────────────────────────────────
        for entry in team_data.get("substitutes", []):
            p = entry.get("player", {})
            records.append({
                "match_id":         match_id,
                "team_api_id":      team_api_id,
                "is_home":          is_home,
                "formation":        formation,
                "fixture_position": "substitutes",
                "player_id":        p.get("id"),
                "player_name":      p.get("name"),
                "player_number":    p.get("number"),
                "player_pos":       p.get("pos"),
                "player_grid":      None,   # reservas não têm grid
                "source":           "api_football",
            })

    return records
