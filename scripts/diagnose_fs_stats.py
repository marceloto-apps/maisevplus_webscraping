"""
Diagnóstico CIRÚRGICO para entender por que SHOTS/PASSES não renderizam.
Salva HTML completo e busca textualmente por 'xGOT', 'Crosses', 'xA'.
Tenta scrollar containers internos.
"""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from camoufox.async_api import AsyncCamoufox
    
    flashscore_id = "IsSHKEbU"
    stats_url = f"https://www.flashscore.com/match/{flashscore_id}/#/match-summary/match-statistics/0"
    
    print("=" * 60)
    print("DIAGNÓSTICO CIRÚRGICO — FLASHSCORE DOM")
    print("=" * 60)
    
    async with AsyncCamoufox(headless=False, os="linux") as browser:
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        print(f"\n[1] Navegando para {stats_url}")
        await page.goto(stats_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(5000)
        
        # Remover cookie
        await page.evaluate("""
            document.querySelectorAll('#onetrust-banner-sdk, #onetrust-consent-sdk, [class*="onetrust"], .ot-sdk-container').forEach(el => el.remove());
            document.body.style.overflow = 'auto';
            document.documentElement.style.overflow = 'auto';
        """)
        await page.wait_for_timeout(1000)
        
        # Diagnóstico 1: buscar "xGOT" no HTML bruto ANTES de scroll
        html_before = await page.content()
        print(f"\n[2] HTML total ANTES do scroll: {len(html_before)} chars")
        print(f"    'xGOT' no HTML? {'SIM ✅' if 'xGOT' in html_before else 'NÃO ❌'}")
        print(f"    'Crosses' no HTML? {'SIM ✅' if 'Crosses' in html_before else 'NÃO ❌'}")
        print(f"    'xA)' no HTML? {'SIM ✅' if 'xA)' in html_before else 'NÃO ❌'}")
        print(f"    'Shots' (seção) no HTML? {'SIM ✅' if '>Shots<' in html_before else 'NÃO ❌'}")
        print(f"    'Passes' (seção) no HTML? {'SIM ✅' if '>Passes<' in html_before else 'NÃO ❌'}")
        
        # Diagnóstico 2: Encontrar containers com scroll
        scrollable_info = await page.evaluate("""
            const results = [];
            document.querySelectorAll('*').forEach(el => {
                const style = getComputedStyle(el);
                if ((style.overflow === 'auto' || style.overflow === 'scroll' || 
                     style.overflowY === 'auto' || style.overflowY === 'scroll') &&
                    el.scrollHeight > el.clientHeight + 50) {
                    const cls = el.className ? el.className.substring(0, 80) : '';
                    const tag = el.tagName;
                    results.push({
                        tag, cls, 
                        scrollH: el.scrollHeight, 
                        clientH: el.clientHeight,
                        id: el.id || ''
                    });
                }
            });
            return results;
        """)
        
        print(f"\n[3] Containers com scroll interno: {len(scrollable_info)}")
        for sc in scrollable_info:
            print(f"    <{sc['tag']}> id='{sc['id']}' class='{sc['cls'][:60]}' scrollH={sc['scrollH']} clientH={sc['clientH']}")
        
        # Diagnóstico 3: Scrollar TODOS os containers internos
        await page.evaluate("""
            document.querySelectorAll('*').forEach(el => {
                const style = getComputedStyle(el);
                if ((style.overflow === 'auto' || style.overflow === 'scroll' || 
                     style.overflowY === 'auto' || style.overflowY === 'scroll') &&
                    el.scrollHeight > el.clientHeight + 50) {
                    el.scrollTo(0, el.scrollHeight);
                }
            });
        """)
        await page.wait_for_timeout(3000)
        
        # Também mouse.wheel
        for _ in range(10):
            await page.mouse.wheel(0, 500)
            await page.wait_for_timeout(300)
        
        # Diagnóstico 4: buscar "xGOT" no HTML DEPOIS de scroll
        html_after = await page.content()
        print(f"\n[4] HTML total DEPOIS do scroll: {len(html_after)} chars")
        print(f"    'xGOT' no HTML? {'SIM ✅' if 'xGOT' in html_after else 'NÃO ❌'}")
        print(f"    'Crosses' no HTML? {'SIM ✅' if 'Crosses' in html_after else 'NÃO ❌'}")  
        print(f"    'xA)' no HTML? {'SIM ✅' if 'xA)' in html_after else 'NÃO ❌'}")
        print(f"    'Shots' (seção) no HTML? {'SIM ✅' if '>Shots<' in html_after else 'NÃO ❌'}")
        print(f"    'Passes' (seção) no HTML? {'SIM ✅' if '>Passes<' in html_after else 'NÃO ❌'}")
        
        # Contar wcl-statistics
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_after, "lxml")
        stats = soup.find_all("div", attrs={"data-testid": "wcl-statistics"})
        print(f"\n[5] Total data-testid='wcl-statistics': {len(stats)}")
        for s in stats:
            cat = s.find(attrs={"data-testid": "wcl-statistics-category"})
            if cat:
                print(f"    -> '{cat.get_text(strip=True)}'")
        
        # Salvar HTML para inspeção
        with open("flashscore_stats_full_dump.html", "w", encoding="utf-8") as f:
            f.write(html_after)
        print("\n[6] HTML salvo em flashscore_stats_full_dump.html")
        
        # Screenshot
        await page.screenshot(path="flashscore_stats_diagnostic.png", full_page=True)
        print("[7] Screenshot salvo em flashscore_stats_diagnostic.png")
        
        await page.close()

if __name__ == "__main__":
    asyncio.run(main())
