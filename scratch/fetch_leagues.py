import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from dotenv import load_dotenv
load_dotenv()
from src.collectors.api_football.client import ApiFootballClient

async def main():
    countries = ['England', 'Scotland', 'Germany', 'France']
    for c in countries:
        res = await ApiFootballClient.get('/leagues', {'country': c})
        print(f"--- {c} ---")
        for x in res:
            print(f"ID: {x['league']['id']} - {x['league']['name']}")

asyncio.run(main())
