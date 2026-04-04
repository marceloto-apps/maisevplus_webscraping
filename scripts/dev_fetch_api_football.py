import asyncio
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collectors.api_football.client import ApiFootballClient

async def main():
    date_str = "2026-04-01"
    print(f"Buscando fixtures para a data {date_str} (league 71)...")
    
    headers = {"x-apisports-key": "11b0151f3fcf9b5522de91b35f6b556b"}
    url = f"https://v3.football.api-sports.io/fixtures"
    
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params={"date": date_str, "league": 71, "season": 2026})
        print(f"API RAW Response: {resp.status_code}")
        data = resp.json()
        print(f"API RAW Body: {data}")
        fixtures = data.get("response", [])
        
    print(f"Fixtures encontradas: {len(fixtures)}")
    if not fixtures:
        return
        
    fixture_id = fixtures[0]["fixture"]["id"]
    print(f"Usando fixture_id = {fixture_id} ({fixtures[0]['teams']['home']['name']} vs {fixtures[0]['teams']['away']['name']})")
    import httpx
    async with httpx.AsyncClient() as client:
        stats = (await client.get("https://v3.football.api-sports.io/fixtures/statistics", headers=headers, params={"fixture": fixture_id})).json().get("response", [])
        events = (await client.get("https://v3.football.api-sports.io/fixtures/events", headers=headers, params={"fixture": fixture_id})).json().get("response", [])
        lineups = (await client.get("https://v3.football.api-sports.io/fixtures/lineups", headers=headers, params={"fixture": fixture_id})).json().get("response", [])
        players = (await client.get("https://v3.football.api-sports.io/fixtures/players", headers=headers, params={"fixture": fixture_id})).json().get("response", [])
    
    data = {
        "fixture_info": fixtures[0],
        "statistics": stats,
        "events": events,
        "lineups": lineups,
        "players": players
    }
    
    with open("api_football_sample.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print("Salvo em api_football_sample.json")

if __name__ == "__main__":
    asyncio.run(main())
