"""Script de diagnóstico para revelar o que o Flashscore está mostrando quando 
a aba de ODDS/COTAÇÕES não é encontrada após a criação de um contexto limpo.

Uso:
  .venv/bin/python scripts/diag_odds_page.py

Este script:
1. Cria um contexto Camoufox limpo
2. Abre a página da partida
3. Aguarda a renderização
4. Captura screenshot em /tmp/flashscore_diag.png
5. Imprime os primeiros 5000 chars do HTML para análise
"""
import asyncio
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        m = await conn.fetchrow("""
            SELECT m.match_id, m.flashscore_id, m.kickoff
            FROM matches m
            WHERE m.league_id = 1
              AND m.status = 'finished'
              AND m.kickoff <= NOW()
              AND m.flashscore_id IS NOT NULL
              AND (m.scraping_flashscore IS NULL OR m.scraping_flashscore = FALSE)
            ORDER BY m.kickoff DESC
            LIMIT 1
        """)
    await pool.close()

    if not m:
        print("Nenhuma partida pendente encontrada.")
        return

    fs_id = m['flashscore_id']
    print(f"Diagnosticando partida: {fs_id} | Kickoff: {m['kickoff']}")
    match_url = f"https://www.flashscore.com/match/{fs_id}/"

    async with AsyncCamoufox(headless=True, os="linux") as browser:
        print("\n[1] Criando contexto LIMPO (sem cookies/localStorage)...")
        context = await browser.new_context(timezone_id="America/Sao_Paulo", locale="pt-BR")
        page = await context.new_page()

        print(f"[2] Navegando para: {match_url}")
        try:
            await page.goto(match_url, wait_until="domcontentloaded", timeout=60000)
            print("[2] page.goto concluido")
        except Exception as e:
            print(f"[2] AVISO timeout: {e}")

        # Screenshot logo após o carregamento
        screenshot_path = "/tmp/flashscore_step1_after_goto.png"
        await page.screenshot(path=screenshot_path, full_page=False)
        print(f"[3] Screenshot 1 salvo em: {screenshot_path}")
        print(f"[3] URL atual: {page.url}")
        title = await page.title()
        print(f"[3] Titulo da pagina: {title}")

        # Checar se modal 18+ está visível
        age_locators = [
            "button:has-text('Eu tenho mais de 18 anos')",
            "button:has-text('18 AND OLDER')",
            "button:has-text('18+')",
            "button:has-text('SOU MAIOR')",
            "a[href*='legal-age']",
            "[class*='ageVerification']",
            "[class*='age-verification']",
            "[class*='legalAge']",
            "[data-testid*='age']",
        ]
        print("\n[4] Verificando presenca do modal de idade (18+):")
        for loc_str in age_locators:
            try:
                cnt = await page.locator(loc_str).count()
                if cnt > 0:
                    txt = await page.locator(loc_str).first.text_content()
                    vis = await page.locator(loc_str).first.is_visible()
                    print(f"  ENCONTRADO ({cnt}x) visible={vis}: {loc_str!r} -> texto: {repr(txt)}")
                else:
                    print(f"  nao encontrado: {loc_str!r}")
            except Exception as ex:
                print(f"  erro: {loc_str!r} -> {ex}")

        # Checar cookie banner
        print("\n[5] Verificando cookie banner:")
        try:
            cnt = await page.locator("button#onetrust-accept-btn-handler").count()
            print(f"  onetrust-accept-btn-handler: {cnt} encontrado(s)")
        except Exception as ex:
            print(f"  erro: {ex}")

        # Checar abas de navegação
        print("\n[6] Verificando abas de navegacao (tablist):")
        try:
            tabs = page.locator("div[role='tablist'] a, div[role='tablist'] button, nav a")
            cnt = await tabs.count()
            print(f"  Total de abas encontradas: {cnt}")
            for i in range(min(cnt, 15)):
                tab = tabs.nth(i)
                txt = await tab.text_content()
                href = await tab.get_attribute("href")
                print(f"  [{i}] texto={repr(txt.strip() if txt else '')} href={repr(href)}")
        except Exception as ex:
            print(f"  erro: {ex}")

        # Links com odds
        print("\n[7] Links com 'cotacoes' ou 'odds' ou 'comparison':")
        try:
            odds_links = page.locator("a[href*='cotacoes'], a[href*='odds'], a[href*='comparison']")
            cnt = await odds_links.count()
            print(f"  Total: {cnt}")
            for i in range(min(cnt, 10)):
                lnk = odds_links.nth(i)
                txt = await lnk.text_content()
                href = await lnk.get_attribute("href")
                print(f"  [{i}] texto={repr(txt.strip() if txt else '')} href={repr(href)}")
        except Exception as ex:
            print(f"  erro: {ex}")

        # Aguardar 5s e tirar outro screenshot
        print("\n[8] Aguardando 5s para renderizacao extra...")
        await page.wait_for_timeout(5000)
        screenshot_path2 = "/tmp/flashscore_step2_after_5s.png"
        await page.screenshot(path=screenshot_path2, full_page=False)
        print(f"[8] Screenshot 2 salvo em: {screenshot_path2}")

        # Re-checar modal após 5s
        print("\n[9] Re-verificando modal de idade apos 5s:")
        for loc_str in age_locators[:4]:
            try:
                cnt = await page.locator(loc_str).count()
                vis = await page.locator(loc_str).first.is_visible() if cnt > 0 else False
                print(f"  {loc_str!r}: count={cnt} visible={vis}")
            except Exception as ex:
                print(f"  {loc_str!r}: erro={ex}")

        # Imprimir primeiros 5000 chars do HTML
        print("\n[10] Primeiros 5000 chars do HTML:")
        html = await page.content()
        print(f"  Total HTML: {len(html)} bytes")
        snippet = html[:5000]
        print("---HTML START---")
        print(snippet)
        print("---HTML END---")

        await context.close()

    print("\nDiagnostico concluido.")
    print("Recupere os screenshots com:")
    print("  scp root@161.97.161.37:/tmp/flashscore_step1_after_goto.png .")
    print("  scp root@161.97.161.37:/tmp/flashscore_step2_after_5s.png .")

if __name__ == "__main__":
    asyncio.run(main())
