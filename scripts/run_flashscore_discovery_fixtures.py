"""
scripts/run_flashscore_discovery_fixtures.py

Discovery diário Flashscore FIXTURES (Partidas Futuras) usando a estratégia
de 2 clusters e limite de 48h por liga ativa.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from src.collectors.flashscore.discovery import FlashscoreDiscovery
from src.collectors.flashscore.config import LEAGUE_FLASHSCORE_PATHS
from src.db.pool import get_pool
from src.db.logger import get_logger

logger = get_logger(__name__)

async def main():
    load_dotenv()
    from src.alerts.telegram_mini import TelegramAlert
    await TelegramAlert.init()
    
    print("Iniciando Discovery de FIXTURES (2 Clusters / Throttle 48h)...")
    discovery = FlashscoreDiscovery()
    pool = await get_pool()
    target_urls = {}
    
    async with pool.acquire() as conn:
        # 1. Obter todas as ligas ativas com temporada atual
        active_leagues = await conn.fetch("""
            SELECT l.league_id, l.code, l.flashscore_path, l.last_fixtures_discovery_at
            FROM leagues l
            JOIN seasons s ON s.league_id = l.league_id
            WHERE l.is_active = TRUE AND s.is_current = TRUE
            ORDER BY l.league_id ASC
        """)
        
        if not active_leagues:
            print("Nenhuma liga ativa com temporada corrente encontrada.")
            await TelegramAlert.close()
            return

        # 2. Dividir em 2 clusters usando o dia do ano
        day_of_year = datetime.now().timetuple().tm_yday
        active_cluster = []
        for idx, l in enumerate(active_leagues):
            # Cluster A (dia par): idx % 2 == 0
            # Cluster B (dia ímpar): idx % 2 == 1
            if (day_of_year % 2 == 0 and idx % 2 == 0) or (day_of_year % 2 != 0 and idx % 2 != 0):
                active_cluster.append(l)

        # 3. Montar target_urls para as ligas do cluster do dia que não rodaram nas últimas 40h
        for l in active_cluster:
            code = l["code"]
            last_run = l["last_fixtures_discovery_at"]
            if last_run:
                if last_run.tzinfo is None:
                    last_run = last_run.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - last_run < timedelta(hours=40):
                    print(f"  -> Liga {code} já teve discovery de fixtures nas últimas 40h (PULANDO).")
                    continue
            
            base_path = l["flashscore_path"] or LEAGUE_FLASHSCORE_PATHS.get(code)
            if base_path:
                urls = [f"https://www.flashscore.com/{base_path}/fixtures/"]
                target_urls[code] = urls

    if not target_urls:
        print("Nenhuma liga do cluster necessita de discovery de fixtures hoje.")
        msg = "🔎 *Flashscore Fixtures Discovery*\nStatus: SKIPPED\nNenhuma liga do cluster do dia necessitava de discovery hoje."
        TelegramAlert.fire("info", msg)
        await asyncio.sleep(1)
        await TelegramAlert.close()
        return

    print(f"Alvos de FIXTURES construídos para {len(target_urls)} ligas.")
    res = await discovery.collect(mode="fixtures", specific_leagues=list(target_urls.keys()), target_urls=target_urls)
    
    print(f"Discovery FIXTURES CONCLUÍDO! Status: {res.status.name}. Matches associados: {res.records_new}")
    
    if res.status.name == "FAILED":
        msg = f"🔎 *Flashscore Fixtures Discovery*\nStatus: FAILED\nErro nas ligas do cluster."
        TelegramAlert.fire("error", msg)
    else:
        # Atualiza a coluna no DB para as ligas executadas com sucesso
        async with pool.acquire() as conn:
            for code in target_urls.keys():
                await conn.execute(
                    "UPDATE leagues SET last_fixtures_discovery_at = NOW() WHERE code = $1", code
                )
        msg = f"🔎 *Flashscore Fixtures Discovery*\nStatus: {res.status.name}\nLigas processadas: {len(target_urls)}\nMatches Associados: {res.records_new}"
        TelegramAlert.fire("info", msg)
        
    await asyncio.sleep(1)
    await TelegramAlert.close()
    
if __name__ == "__main__":
    asyncio.run(main())
