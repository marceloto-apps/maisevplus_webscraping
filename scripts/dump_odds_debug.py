"""
Script de diagnóstico: salva o HTML completo da página de odds 
e verifica quais elementos relevantes existem no DOM.
Rode na VPS: .venv/bin/python scripts/dump_odds_debug.py
"""
import asyncio
from camoufox.async_api import AsyncCamoufox

# Match que sabemos ter odds (Gremio vs Remo, jogo já aconteceu)
MATCH_ID = "IsSHKEbU"

async def main():
    async with AsyncCamoufox(headless=True, os="linux") as browser:
        page = await browser.new_page()
        
        # PASSO 1: Acessar o match base para resolver slug
        base_url = f"https://www.flashscore.com/match/{MATCH_ID}/"
        print(f"[1] Navegando para {base_url}")
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"    Timeout, mas continuando... {e}")
        
        # Esperar abas carregarem
        try:
            await page.wait_for_selector("a[href*='/odds/']", timeout=15000)
            print("    ✅ Link /odds/ encontrado no DOM")
        except:
            print("    ❌ Link /odds/ NÃO encontrado no DOM")
            await page.wait_for_timeout(5000)
        
        # Extrair URL final e verificar redirecionamento
        final_url = page.url
        print(f"    URL final: {final_url}")
        
        # Listar todas as abas disponíveis
        all_links = await page.query_selector_all("a[href]")
        tabs = []
        for link in all_links:
            href = await link.get_attribute("href")
            text = await link.inner_text()
            if href and "/match/" in href and text.strip():
                tabs.append(f"  {text.strip()} -> {href}")
        print(f"\n    Abas da partida encontradas ({len(tabs)}):")
        for t in tabs[:20]:
            print(f"    {t}")
        
        # PASSO 2: Tentar clicar na aba Odds em vez de navegar diretamente
        print(f"\n[2] Tentando CLICAR na aba 'Odds'...")
        odds_tab = await page.query_selector("a[href*='/odds/']")
        if odds_tab:
            await odds_tab.click()
            print("    ✅ Cliquei na aba Odds")
            
            # Esperar renderização
            try:
                await page.wait_for_selector("div.ui-table__row", timeout=15000)
                print("    ✅ div.ui-table__row apareceu!")
            except:
                print("    ❌ div.ui-table__row NÃO apareceu após clique")
                # Tenta outro seletor
                try:
                    await page.wait_for_selector("a.oddsCell__odd", timeout=5000)
                    print("    ✅ a.oddsCell__odd apareceu!")
                except:
                    print("    ❌ a.oddsCell__odd também não apareceu")
                    
                # Tenta esperar qualquer conteúdo de odds
                try:
                    await page.wait_for_selector("[class*='odds']", timeout=5000)
                    print("    ✅ Elemento com 'odds' na classe encontrado")
                except:
                    print("    ❌ Nenhum elemento com 'odds' na classe")
            
            # Verificar URL após clique
            print(f"    URL após clique: {page.url}")
        else:
            print("    ❌ Aba Odds não encontrada para clicar")
        
        # PASSO 3: Agora salvar o HTML completo
        html = await page.content()
        
        with open("flashscore_odds_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n[3] HTML salvo em flashscore_odds_debug.html ({len(html)} bytes)")
        
        # PASSO 4: Análise do DOM
        print("\n[4] Análise do DOM:")
        
        checks = [
            ("div.ui-table__row", "Linhas da tabela de odds"),
            ("a.oddsCell__odd", "Células de odds individuais"),
            ("div.oddsCell__bookmakerPart", "Bookmaker cells"),
            ("[class*='tabContent__odds']", "Tab content odds"),
            ("[class*='odds-comparison']", "Odds comparison container"),
            ("div.filterOver", "Filter overlay (sub-abas)"),
            ("div[class*='table']", "Qualquer div com 'table'"),
            ("img[alt='bet365']", "Logo bet365"),
            ("div[data-analytics-bookmaker-id]", "Bookmaker rows (data attr)"),
        ]
        
        for selector, desc in checks:
            els = await page.query_selector_all(selector)
            status = f"✅ {len(els)} encontrados" if els else "❌ 0"
            print(f"    {desc}: {status}")
        
        # PASSO 5: Contar classes únicas com 'odd' no nome
        print("\n[5] Classes com 'odd' no nome:")
        odd_classes = await page.evaluate("""
            () => {
                const all = document.querySelectorAll('[class*="odd"]');
                const classes = new Set();
                all.forEach(el => { 
                    el.classList.forEach(c => { if (c.toLowerCase().includes('odd')) classes.add(c); });
                });
                return Array.from(classes).slice(0, 20);
            }
        """)
        for c in odd_classes:
            print(f"    - {c}")
        if not odd_classes:
            print("    (nenhuma)")
        
        # PASSO 6: Mostrar o conteúdo principal (section/main/detail)
        print("\n[6] Conteúdo da div#detail (primeiros 2000 chars):")
        detail = await page.query_selector("#detail")
        if detail:
            detail_html = await detail.inner_html()
            print(detail_html[:2000])
        else:
            print("    div#detail não encontrada")

        await page.close()

asyncio.run(main())
