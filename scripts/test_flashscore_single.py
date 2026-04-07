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
    flashscore_id = "jHs8giMs"
    
    async with pool.acquire() as conn:
        # Pega o match_id
        row = await conn.fetchrow("SELECT match_id FROM matches WHERE flashscore_id = $1", flashscore_id)
        if not row:
            print(f"❌ Erro: Match com flashscore_id '{flashscore_id}' não encontrado no DB.")
            return
            
        match_uuid = row['match_id']
        print(f"✅ Encontrado DB ID para {flashscore_id}: {match_uuid}")

        # Limitamos ao mercado principal para ser mais rápido
        collector = FlashscoreOddsCollector(["1x2_ft"])
        await collector._init_bm_ids(conn)
        
        print("\n⏳ Inicializando Camoufox e disparando coleta...")
        async with AsyncCamoufox(headless=False, os="linux") as browser:
            print(f"▶️ Simulando coleta da fila para a partida específica...")
            # Collect odds and stats
            inserted = await collector.collect_match(browser, conn, str(match_uuid), flashscore_id, True, "test_job_stats")
            print(f"✅ Entradas de odds inseridas: {inserted}")
            
            # Debug extra: abrir a aba stats com scroll e listar TUDO
            print("\n============================================================")
            print("EXTRA DEBUG - INSPECTING DOM FOR STATS WITH SCROLL...")
            from bs4 import BeautifulSoup
            page = await browser.new_page()
            await page.goto(f"https://www.flashscore.com/match/{flashscore_id}/#/match-summary/match-statistics/0")
            await page.wait_for_timeout(4000)
            
            # Scroll 5x para forçar lazy-render
            for i in range(5):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)
            
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            # Primeiro: listar TODAS as classes de divs que tenham "stat" no nome
            all_stat_divs = soup.find_all("div", class_=lambda c: c and "stat" in str(c).lower())
            print(f"\nTotal divs com 'stat' na classe: {len(all_stat_divs)}")
            seen_classes = set()
            for d in all_stat_divs:
                cls = " ".join(d.get("class", []))
                if cls not in seen_classes:
                    seen_classes.add(cls)
                    print(f"  CLASS: '{cls}'")
            
            # Segundo: encontrar categorias
            rows = soup.find_all("div", class_=lambda c: c and ("row" in str(c).lower() or "stat" in str(c).lower()))
            print(f"\nTotal linhas candidatas (row|stat): {len(rows)}")
            print("Categorias encontradas:")
            for r in rows:
                cat = r.find(class_=lambda c: c and "category" in str(c).lower())
                if cat:
                    full_text = cat.get_text(strip=True)
                    print(f"  -> '{full_text}'")
            
            await page.close()
            
        print("\n🔍 Checando a tabela 'match_stats' no banco de dados:")
        stats = await conn.fetchrow(
            "SELECT xg_fs_home, xg_fs_away, xgot_fs_home, xgot_fs_away, xa_fs_home, xa_fs_away, crosses_fs_home, crosses_fs_away FROM match_stats WHERE match_id = $1", 
            match_uuid
        )
        
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
