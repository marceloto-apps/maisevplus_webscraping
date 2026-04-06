import sys
import os
import asyncio
from bs4 import BeautifulSoup
from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collectors.flashscore.config import FlashscoreConfig

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

    browser_config = FlashscoreConfig.get_camoufox_config()
    
    # Optional setup for stats URL if needed
    try:
        async with AsyncCamoufox(**browser_config) as browser:
            page = await browser.new_page()
            
            # Route interception to avoid unnecessary loads
            await page.route("**/*", lambda route: 
                route.continue_() if route.request.resource_type in ["document", "script", "xhr", "fetch"] 
                else route.abort()
            )

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            print("    ✅ DOM carregado! Esperando seletor de estatísticas...")
            
            # The general category wrapper often is .stat__category or .section
            try:
                # wait for stat rows to appear
                await page.wait_for_selector(".stat__category", timeout=15000)
                print("    ✅ Estatísticas renderizadas!")
            except Exception as e:
                print(f"    ⚠️ Falha ao esperar estatísticas: {e}")

            html = await page.content()
            
            print("\n[2] Analisando o HTML...")
            soup = BeautifulSoup(html, "lxml")
            
            stat_rows = soup.find_all("div", class_="stat__category")
            print(f"    Encontradas {len(stat_rows)} linhas de estatísticas.")
            
            stats_dict = {}

            for row in stat_rows:
                category_name_tag = row.find("div", class_="wld--category") or row.find("div", class_="stat__categoryName")
                if not category_name_tag:
                    continue
                    
                category_name = category_name_tag.text.strip()
                
                # Usually home is first, away is second OR class specific
                home_val_tag = row.find("div", class_="stat__homeValue") or row.find("div", class_="stat__value stat__value--home")
                away_val_tag = row.find("div", class_="stat__awayValue") or row.find("div", class_="stat__value stat__value--away")
                
                # Try generic finding if classes are slightly different
                if not home_val_tag or not away_val_tag:
                    values = row.find_all("div", class_="stat__value")
                    if len(values) >= 2:
                        home_val_tag = values[0]
                        away_val_tag = values[1]

                if home_val_tag and away_val_tag:
                    home_val = home_val_tag.text.strip()
                    away_val = away_val_tag.text.strip()
                    print(f"    -> {category_name}: {home_val} (Home) / {away_val} (Away)")
                    stats_dict[category_name] = {"home": home_val, "away": away_val}

            print("\n[3] Buscando estatísticas requeridas:")
            required = ["Expected Goals (xG)", "xG", "Expected Goals on target (xGOT)", "xGOT", "Crosses", "Expected Assists (xA)", "xA"]
            
            for req in required:
                # Attempt to find exactly or partially
                matched = False
                for cat, vals in stats_dict.items():
                    if req.lower() in cat.lower():
                        print(f"    🟢 Encontrado '{req}' (na página: '{cat}'): Home={vals['home']}, Away={vals['away']}")
                        matched = True
                        break
                if not matched:
                    print(f"    🔴 Não encontrado: '{req}'")

            print("\n[4] Salvando HTML para debug local ('flashscore_stats_dump.html')")
            with open("flashscore_stats_dump.html", "w", encoding="utf-8") as f:
                f.write(soup.prettify())

    except Exception as e:
        print(f"    ❌ ERRO FATAL NO BROWSER: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
