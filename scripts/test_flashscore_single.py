import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector

async def try_import_camoufox():
    try:
        from camoufox.async_api import AsyncCamoufox
        return AsyncCamoufox
    except ImportError:
        print("❌ Camoufox framework missing.")
        return None

async def main():
    print("============================================================")
    print("TESTE FLASHSCORE SINGULAR — IsSHKEbU")
    print("============================================================")

    AsyncCamoufox = await try_import_camoufox()
    if not AsyncCamoufox:
        return

    pool = await get_pool()
    flashscore_id = "IsSHKEbU"
    
    async with pool.acquire() as conn:
        # Pega o match_id
        row = await conn.fetchrow("SELECT match_id FROM matches WHERE flashscore_id = $1", flashscore_id)
        if not row:
            print(f"❌ Erro: Match com flashscore_id '{flashscore_id}' não encontrado no DB.")
            return
            
        match_uuid = row['match_id']
        print(f"✅ Encontrado DB ID para {flashscore_id}: {match_uuid}")

        # Limitamos ao mercado principal para ser mais rápido (ele raspará a tab Odds e depios as Estatísticas)
        collector = FlashscoreOddsCollector(["1x2_ft"])
        await collector._init_bm_ids(conn)
        
        print("\n⏳ Inicializando Camoufox e disparando coleta...")
        async with AsyncCamoufox(headless=False, os="linux") as browser:
            print(f"▶️ Simulando coleta da fila para a partida específica...")
            inserted = await collector.collect_match(browser, conn, str(match_uuid), flashscore_id, True, "test_job_stats")
            print(f"✅ Entradas de odds inseridas: {inserted}")
            
        print("\n🔍 Checando a tabela 'match_stats' no banco de dados:")
        stats = await conn.fetchrow("SELECT xg_fs_home, xg_fs_away, xgot_fs_home, xa_fs_home, crosses_fs_home, crosses_fs_away FROM match_stats WHERE match_id = $1 AND source = 'flashscore'", match_uuid)
        
        if stats:
            print(f"  📊 ESTATÍSTICAS NATIVAS DO FLASHSCORE CONFIRMADAS NO BANCO:")
            for k, v in stats.items():
                print(f"    - {k}: {v}")
        else:
            print(f"  ❌ Nenhuma estatística salva no database para {match_uuid}.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
