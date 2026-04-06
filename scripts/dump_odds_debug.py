"""
Script de diagnóstico: testa o proxy NordVPN e verifica quais bookmakers aparecem.
Rode na VPS: xvfb-run .venv/bin/python scripts/dump_odds_debug.py
"""
import asyncio
import os
from dotenv import load_dotenv
from camoufox.async_api import AsyncCamoufox

load_dotenv()

# Match que sabemos ter odds (Gremio vs Remo)
MATCH_ID = "IsSHKEbU"

async def main():
    # Monta proxy config
    proxy_server = os.getenv("NORDVPN_PROXY_SERVER")
    proxy_user = os.getenv("NORDVPN_PROXY_USER")
    proxy_pass = os.getenv("NORDVPN_PROXY_PASS")
    
    camoufox_kwargs = {"headless": False, "os": "linux"}
    
    if proxy_server and proxy_user and proxy_pass:
        camoufox_kwargs["proxy"] = {
            "server": proxy_server,
            "username": proxy_user,
            "password": proxy_pass,
        }
        camoufox_kwargs["geoip"] = True
        print(f"✅ Proxy configurado: {proxy_server}")
    else:
        print("⚠️  Sem proxy! Bookmakers serão regionais (FR).")
        print(f"   NORDVPN_PROXY_SERVER={proxy_server}")
    
    async with AsyncCamoufox(**camoufox_kwargs) as browser:
        page = await browser.new_page()
        
        # PASSO 1: Verificar IP/região
        print("\n[1] Verificando IP/região...")
        try:
            await page.goto("https://ifconfig.me/ip", wait_until="domcontentloaded", timeout=15000)
            ip_text = await page.inner_text("body")
            print(f"    IP público: {ip_text.strip()}")
        except Exception as e:
            print(f"    Erro ao verificar IP: {e}")
        
        # PASSO 2: Navegar para o match
        base_url = f"https://www.flashscore.com/match/{MATCH_ID}/"
        print(f"\n[2] Navegando para {base_url}")
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"    Timeout, mas continuando... {e}")
        
        # Esperar abas
        try:
            await page.wait_for_selector("a[href*='/odds/']", timeout=15000)
            print("    ✅ Link /odds/ encontrado")
        except:
            print("    ❌ Link /odds/ NÃO encontrado")
            await page.wait_for_timeout(5000)
        
        # PASSO 3: Clicar na aba Odds
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
            return
        
        # PASSO 4: Listar TODOS os bookmakers que aparecem
        print(f"\n[4] Bookmakers encontrados no DOM:")
        bm_imgs = await page.query_selector_all("div.ui-table__row img")
        bm_names = set()
        for img in bm_imgs:
            alt = await img.get_attribute("alt")
            if alt:
                bm_names.add(alt)
        
        for name in sorted(bm_names):
            print(f"    📌 {name}")
        
        if not bm_names:
            print("    (nenhum bookmaker encontrado)")
        
        # PASSO 5: Mostrar valores de odds da primeira row
        print(f"\n[5] Primeira row de odds:")
        first_row = await page.query_selector("div.ui-table__row")
        if first_row:
            odds_cells = await first_row.query_selector_all("a.oddsCell__odd span")
            for cell in odds_cells:
                text = await cell.inner_text()
                text = text.strip()
                if text:
                    print(f"    Odd: {text}")
        
        await page.close()

asyncio.run(main())
