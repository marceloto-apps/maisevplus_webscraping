import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from src.collectors.flashscore.discovery import FlashscoreDiscovery
from src.db.logger import configure_logging, get_logger

configure_logging()
logger = get_logger("run_flashscore_discovery")

async def main():
    logger.info("Iniciando Discovery de Results para Brasileirão (BRA_SA)...")
    discovery = FlashscoreDiscovery()
    # Coleta a aba /results/
    res = await discovery.collect(mode="results", specific_leagues=["BRA_SA"])
    logger.info(f"Discovery CONCLUÍDO! Status: {res.status.name}. Matches atualizados com flashscore_id: {res.records_collected}")
    
    # Executamos tabmém o de fixtures (jogos a realizar) caso o ano atual ainda tenha jogos em andamento?
    # Como queremos testar o backfill (partidas finalizadas), "results" é o suficiente!
    
if __name__ == "__main__":
    asyncio.run(main())
