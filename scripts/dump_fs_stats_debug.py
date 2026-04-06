import sys
import os
import asyncio
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def try_import_camoufox():
    try:
        from camoufox.async_api import AsyncCamoufox
        return AsyncCamoufox
    except ImportError as e:
        print(f"❌ Camoufox framework missing: {e}")
        return None

async def main():
    print("============================================================")
    print("DEBUG FLASHSCORE STATS — NORDVPN / CAMOUFOX")
    print("============================================================")

    AsyncCamoufox = await try_import_camoufox()
    if not AsyncCamoufox:
        return

    # Use a generic match that has stats
    match_id = "IsSHKEbU"
    url = f"https://www.flashscore.com/match/{match_id}/#/match-summary/match-statistics/0"
    
    print(f"\n[1] Navegando para {url}")

    try:
        async with AsyncCamoufox(headless=False, os="linux") as browser:
            page = await browser.new_page()
            
            # No route interception to ensure full SPA load
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            print("    ✅ DOM carregado! Esperando renderização do SPA (5 segs)...")
            await page.wait_for_timeout(5000)
            
            # Screenshot to check what is rendered
            await page.screenshot(path="flashscore_stats_screenshot.png")
            print("    📸 Screenshot salvo como flashscore_stats_screenshot.png")

            # Busca divs contendo o texto 'xG' ou qualquer estatística para descobrir a classe
            html = await page.content()
            
            print("\n[2] Analisando o HTML...")
            soup = BeautifulSoup(html, "lxml")
            
            stat_rows = soup.find_all("div", attrs={"class": lambda c: c and ("stat" in c.lower() or "row" in c.lower())})
            print(f"    Encontradas {len(stat_rows)} divs candidatas para 'row' ou 'stat'.")
            
            print("\n[3] Buscando os textos desejados diretamente nas Tags:")
            
            # Uma abordagem bruta: varrer todo o texto tentando achar 'xG'
            found_any = False
            for div in soup.find_all(string=True):
                text = div.strip()
                if text in ["Expected Goals (xG)", "xG", "Expected Goals on target (xGOT)", "xGOT", "Crosses", "Expected Assists (xA)", "xA"]:
                    parent = div.parent
                    grandparent = parent.parent if parent else None
                    print(f"    !! ACHOU -> '{text}'")
                    if grandparent:
                        print(f"       Grandpa Class: '{grandparent.get('class')}'")
                        print(f"       Conteúdo completo: {grandparent.get_text(' | ', strip=True)}")
                    found_any = True

            if not found_any:
                print("    🔴 Nenhuma das palavras exatas (xG, xGOT, etc) foi encontrada textualmente no DOM.")
            
            print("\n[4] Salvando HTML para debug local ('flashscore_stats_dump.html')")
            with open("flashscore_stats_dump.html", "w", encoding="utf-8") as f:
                f.write(soup.prettify())

    except Exception as e:
        print(f"    ❌ ERRO FATAL NO BROWSER: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
