"""
scripts/run_flashscore_discovery_all.py

Discovery diário de Flashscore IDs para temporadas ATUAIS (e imediatamente anterior).
Roda pelo scheduler (06:00 BRT) para manter os flashscore_ids atualizados.

Para discovery histórico de TODAS as temporadas, usar:
    scripts/run_flashscore_discovery_historical.py

Uso (scheduler/cron):
    xvfb-run -a python scripts/run_flashscore_discovery_all.py
"""
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

def build_flashscore_season_slug(label: str) -> str:
    """
    Converte label de temporada para slug de URL do Flashscore.
    Exemplos:
        '2024/2025' -> '2024-2025'
        '2025'      -> '2025'
        '24/25'     -> '2024-2025'  (fallback legado)
    """
    if "/" in label:
        parts = label.split("/")
        p1, p2 = parts[0].strip(), parts[1].strip()
        y1 = f"20{p1}" if len(p1) == 2 else p1
        y2 = f"20{p2}" if len(p2) == 2 else p2
        return f"{y1}-{y2}"
    return label

async def main():
    from src.alerts.telegram_mini import TelegramAlert
    await TelegramAlert.init()
    
    print("Iniciando Discovery Diário Flashscore (temporadas atuais)...")
    discovery = FlashscoreDiscovery()
    pool = await get_pool()
    target_urls = {}
    
    async with pool.acquire() as conn:
        # Itera sobre ligas com flashscore_path configurado no dicionário Python
        for code, base_path in LEAGUE_FLASHSCORE_PATHS.items():
            # Verifica se a liga está ativa no banco
            league_id = await conn.fetchval(
                "SELECT league_id FROM leagues WHERE code = $1 AND is_active = TRUE", code
            )
            if not league_id:
                continue

            # Temporada atual e as 4 anteriores (limite 5, mais nova primeiro)
            seasons = await conn.fetch("""
                SELECT label, is_current FROM seasons 
                WHERE league_id = $1
                ORDER BY label DESC LIMIT 5
            """, league_id)
                
            urls = []
            for s in seasons:
                label = s["label"]
                if s.get("is_current"):
                    urls.append(f"https://www.flashscore.com/{base_path}/results/")
                else:
                    slug = build_flashscore_season_slug(label)
                    urls.append(f"https://www.flashscore.com/{base_path}-{slug}/results/")
            
            if urls:
                target_urls[code] = urls

    print(f"Alvos construídos para {len(target_urls)} ligas.")
    
    res = await discovery.collect(mode="results", specific_leagues=list(target_urls.keys()), target_urls=target_urls)
    
    print(f"Discovery GLOBAL CONCLUÍDO! Status: {res.status.name}. Matches atualizados: {res.records_new}")
    
    msg = f"🔍 *Flashscore Mass Discovery*\nStatus: {res.status.name}\nMatches Associados: {res.records_new}"
    if res.status.name == "FAILED":
        TelegramAlert.fire("error", msg)
    else:
        TelegramAlert.fire("info", msg)
        
    await asyncio.sleep(1)
    await TelegramAlert.close()
    
if __name__ == "__main__":
    asyncio.run(main())
