"""
Script de diagnóstico: verifica quais bookmakers aparecem no Flashscore.
A VPS deve estar conectada ao NordVPN Brasil antes de rodar.
Rode: xvfb-run .venv/bin/python scripts/dump_odds_debug.py
"""
import asyncio
from camoufox.async_api import AsyncCamoufox

MATCH_ID = "IsSHKEbU"  # Gremio vs Remo

async def main():
    async with AsyncCamoufox(headless=False, os="linux") as browser:
        page = await browser.new_page()
        
        # 1. Verificar IP
        print("[1] Verificando IP/região...")
        try:
            await page.goto("https://ifconfig.me/ip", wait_until="domcontentloaded", timeout=15000)
            ip_text = await page.inner_text("body")
            print(f"    IP público: {ip_text.strip()}")
        except Exception as e:
            print(f"    Erro ao verificar IP: {e}")
        
        # 2. Navegar para o match
        base_url = f"https://www.flashscore.com/match/{MATCH_ID}/"
        print(f"\n[2] Navegando para {base_url}")
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"    Timeout, continuando... {e}")
        
        try:
            await page.wait_for_selector("a[href*='/odds/']", timeout=15000)
            print("    ✅ Link /odds/ encontrado")
        except:
            print("    ❌ Link /odds/ NÃO encontrado")
            await page.wait_for_timeout(5000)
        
        # 3. Clicar na aba Odds
        print(f"\n[3] Clicando na aba Odds...")
        odds_tab = await page.query_selector("a[href*='/odds/']")
        if odds_tab:
            await odds_tab.click()
            try:
                await page.wait_for_selector("div.ui-table__row", timeout=15000)
                print("    ✅ Tabela de odds carregou!")
            except:
                print("    ❌ Tabela de odds NÃO carregou")
        else:
            print("    ❌ Aba Odds não encontrada")
            await page.close()
            return
        
        # 4. Listar bookmakers
        print(f"\n[4] Bookmakers encontrados:")
        bm_imgs = await page.query_selector_all("div.ui-table__row img")
        bm_names = set()
        for img in bm_imgs:
            alt = await img.get_attribute("alt")
            if alt:
                bm_names.add(alt)
        for name in sorted(bm_names):
            print(f"    📌 {name}")
        if not bm_names:
            print("    (nenhum)")
        
        # 5. Odds da primeira row
        print(f"\n[5] Primeira row de odds:")
        first_row = await page.query_selector("div.ui-table__row")
        if first_row:
            odds_cells = await first_row.query_selector_all("a.oddsCell__odd span")
            for cell in odds_cells:
                text = (await cell.inner_text()).strip()
                if text:
                    print(f"    Odd: {text}")
        
        await page.close()

asyncio.run(main())
