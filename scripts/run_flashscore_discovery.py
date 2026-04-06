import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from src.collectors.flashscore.discovery import FlashscoreDiscovery

async def main():
    print("Iniciando Discovery de Results para Brasileirão (BRA_SA)...")
    discovery = FlashscoreDiscovery()
    # Coleta a aba /results/
    res = await discovery.collect(mode="results", specific_leagues=["BRA_SA"])
    print(f"Discovery CONCLUÍDO! Status: {res.status.name}. Matches atualizados com flashscore_id: {res.records_collected}")
    
if __name__ == "__main__":
    asyncio.run(main())
