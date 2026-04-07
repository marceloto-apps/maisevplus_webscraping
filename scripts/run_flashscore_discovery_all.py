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
    """Conserta label '23/24' para '2023-2024' e '2023' para '2023'."""
    if "/" in label:
        parts = label.split("/")
        # Assumindo que 23 é 2023
        y1 = f"20{parts[0]}"
        y2 = f"20{parts[1]}"
        return f"{y1}-{y2}"
    return label

async def main():
    print("Iniciando Discovery Massivo Flashscore...")
    discovery = FlashscoreDiscovery()
    pool = await get_pool()
    target_urls = {}
    
    async with pool.acquire() as conn:
        # Pega todas as ligas configuradas pro Flashscore (ativo)
        leagues = await conn.fetch("SELECT code, flashscore_path FROM leagues WHERE is_active = TRUE AND flashscore_path IS NOT NULL")
        
        for lg in leagues:
            code = lg["code"]
            base_path = lg["flashscore_path"] # ex: "football/brazil/serie-a-betano"
            
            # Decide quais seasons buscar
            if code in ["BRA_SA", "ENG_PL"]:
                # APENAS temporada passada (pois a atual já rodou)
                seasons = await conn.fetch("SELECT label, is_current FROM seasons WHERE league_id = (SELECT league_id FROM leagues WHERE code = $1) AND is_current = FALSE ORDER BY label DESC LIMIT 1", code)
            else:
                # Temporada atual e Imediatamente Anterior (limite 2 ordered by label desc)
                seasons = await conn.fetch("SELECT label, is_current FROM seasons WHERE league_id = (SELECT league_id FROM leagues WHERE code = $1) ORDER BY label DESC LIMIT 2", code)
                
            urls = []
            for s in seasons:
                label = s["label"]
                # Se for a atual, a url base /results/ já funciona
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
    
if __name__ == "__main__":
    asyncio.run(main())
