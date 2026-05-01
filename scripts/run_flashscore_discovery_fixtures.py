import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from src.collectors.flashscore.discovery import FlashscoreDiscovery
from src.collectors.flashscore.config import LEAGUE_FLASHSCORE_PATHS
from src.db.pool import get_pool
from src.db.logger import get_logger

logger = get_logger(__name__)

async def main():
    from src.alerts.telegram_mini import TelegramAlert
    await TelegramAlert.init()
    
    print("Iniciando Discovery Diário Flashscore FIXTURES (Partidas Futuras)...")
    discovery = FlashscoreDiscovery()
    pool = await get_pool()
    target_urls = {}
    
    async with pool.acquire() as conn:
        for code, base_path in LEAGUE_FLASHSCORE_PATHS.items():
            league_id = await conn.fetchval(
                "SELECT league_id FROM leagues WHERE code = $1 AND is_active = TRUE", code
            )
            if not league_id:
                continue

            # Para fixtures só importam as partidas que estão de fato para acontecer, 
            # portanto a URL default `base_path/fixtures/` é suficiente para Flashscore
            urls = [f"https://www.flashscore.com/{base_path}/fixtures/"]
            target_urls[code] = urls

    print(f"Alvos de FIXTURES construídos para {len(target_urls)} ligas.")
    
    res = await discovery.collect(mode="fixtures", specific_leagues=list(target_urls.keys()), target_urls=target_urls)
    
    print(f"Discovery FIXTURES CONCLUÍDO! Status: {res.status.name}. Matches atualizados: {res.records_new}")
    
    msg = f"🔎 *Flashscore Fixtures Discovery*\nStatus: {res.status.name}\nMatches Associados: {res.records_new}"
    if res.status.name == "FAILED":
        TelegramAlert.fire("error", msg)
    else:
        TelegramAlert.fire("info", msg)
        
    await asyncio.sleep(1)
    await TelegramAlert.close()
    
if __name__ == "__main__":
    asyncio.run(main())
