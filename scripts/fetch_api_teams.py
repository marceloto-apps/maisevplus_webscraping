import asyncio
import os
import sys
import httpx

async def main():
    headers = {"x-apisports-key": "11b0151f3fcf9b5522de91b35f6b556b"}
    url = "https://v3.football.api-sports.io/teams"
    params = {"league": 71, "season": 2026}
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        data = resp.json().get("response", [])
        
    print("\n--- Lista de Times (Brasileirão 2026 - API-Football) ---")
    for t in data:
        team = t.get("team", {})
        print(f"ID API: {team.get('id')} | Nome API: {team.get('name')} | Canonical/DB ID: ________")

if __name__ == "__main__":
    asyncio.run(main())
