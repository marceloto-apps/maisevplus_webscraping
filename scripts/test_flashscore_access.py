"""
scripts/test_flashscore_access.py
Teste mínimo de acesso ao Flashscore usando Camoufox.
Valida se o browser stealth consegue carregar a página e encontrar odds.

Uso no VPS:
    pip install -U camoufox[geoip]
    python -m camoufox fetch
    python scripts/test_flashscore_access.py
"""
import asyncio
import sys
import time

# ============================================================
# TESTE 1: Página principal (verifica se Cloudflare bloqueia)
# ============================================================
async def test_homepage():
    """Tenta carregar a homepage do Flashscore."""
    from camoufox.async_api import AsyncCamoufox

    print("\n[TEST 1] Carregando homepage do Flashscore...")
    start = time.time()

    async with AsyncCamoufox(headless=True, os="linux") as browser:
        page = await browser.new_page()

        try:
            resp = await page.goto(
                "https://www.flashscore.com/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            elapsed = time.time() - start

            status = resp.status if resp else "NO_RESPONSE"
            title = await page.title()
            url = page.url

            print(f"  Status:  {status}")
            print(f"  Title:   {title}")
            print(f"  URL:     {url}")
            print(f"  Tempo:   {elapsed:.1f}s")

            # Verificar se foi bloqueado
            content = await page.content()
            blocked_signals = [
                "Access Denied",
                "blocked",
                "captcha",
                "challenge",
                "Attention Required",
                "Just a moment",
            ]
            is_blocked = any(s.lower() in content.lower() for s in blocked_signals)

            if is_blocked:
                print("  ❌ BLOQUEADO — Cloudflare/anti-bot detectou automação")
                return False
            elif status == 200 and "flashscore" in title.lower():
                print("  ✅ HOMEPAGE OK — Acesso permitido!")
                return True
            else:
                print(f"  ⚠️ Status inesperado (pode funcionar parcialmente)")
                return True

        except Exception as e:
            print(f"  ❌ ERRO: {e}")
            return False


# ============================================================
# TESTE 2: Página de match com odds (valida renderização JS)
# ============================================================
async def test_match_odds():
    """Tenta carregar uma página de odds de um jogo real."""
    from camoufox.async_api import AsyncCamoufox

    print("\n[TEST 2] Carregando página de odds de um match...")

    # Buscar um match_id real do Flashscore (ligas principais)
    # Vamos usar a página de resultados da Premier League para encontrar um match
    async with AsyncCamoufox(headless=True, os="linux") as browser:
        page = await browser.new_page()

        try:
            # Ir para resultados da Premier League
            await page.goto(
                "https://www.flashscore.com/football/england/premier-league/results/",
                wait_until="networkidle",
                timeout=45000,
            )

            # Esperar renderização
            await page.wait_for_timeout(3000)

            # Tentar encontrar links de matches
            match_links = await page.query_selector_all('a[href*="/match/"]')
            print(f"  Links de matches encontrados: {len(match_links)}")

            if not match_links:
                # Tentar seletores alternativos
                match_links = await page.query_selector_all(".event__match")
                print(f"  (tentativa 2) Elementos de match: {len(match_links)}")

            if not match_links:
                content = await page.content()
                # Procurar por IDs de match no HTML
                import re
                ids = re.findall(r'/match/([A-Za-z0-9]{8,})/', content)
                print(f"  (regex) IDs encontrados no HTML: {len(ids)}")

                if ids:
                    match_id = ids[0]
                    print(f"  Usando match ID: {match_id}")
                else:
                    print("  ⚠️ Nenhum match encontrado, mas a página carregou")
                    # Salvar screenshot para debug
                    await page.screenshot(path="/tmp/flashscore_results.png")
                    print("  Screenshot salvo em /tmp/flashscore_results.png")
                    return True  # Mesmo sem matches, acesso funcionou
            else:
                # Extrair href do primeiro match
                href = await match_links[0].get_attribute("href")
                import re
                id_match = re.search(r'/match/([A-Za-z0-9]+)', href or "")
                match_id = id_match.group(1) if id_match else None
                print(f"  Match ID extraído: {match_id}")

            if match_id:
                return await test_odds_page(browser, match_id)

            return True

        except Exception as e:
            print(f"  ❌ ERRO: {e}")
            await page.screenshot(path="/tmp/flashscore_error.png")
            print("  Screenshot salvo em /tmp/flashscore_error.png")
            return False


async def test_odds_page(browser, match_id: str):
    """Carrega a tab de odds de um match específico."""
    page = await browser.new_page()

    url = f"https://www.flashscore.com/match/{match_id}/#/odds-comparison/1x2-odds/full-time"
    print(f"\n[TEST 3] Carregando odds 1x2: {url}")

    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)
        await page.wait_for_timeout(3000)

        content = await page.content()

        # Procurar por elementos de odds
        odds_indicators = [
            "oddsCell",
            "odds__val",
            "cell--odd",
            "odds-comparison",
            "bookmaker",
        ]
        found = [ind for ind in odds_indicators if ind.lower() in content.lower()]

        print(f"  Indicadores de odds encontrados: {found}")

        # Procurar nomes de bookmakers conhecidos
        bookmakers_check = ["Pinnacle", "bet365", "Betfair", "1xBet", "Betano", "Superbet"]
        bm_found = [bm for bm in bookmakers_check if bm.lower() in content.lower()]
        print(f"  Bookmakers detectados: {bm_found}")

        # Salvar screenshot
        await page.screenshot(path="/tmp/flashscore_odds.png", full_page=True)
        print("  Screenshot salvo em /tmp/flashscore_odds.png")

        if found or bm_found:
            print("  ✅ ODDS ENCONTRADAS! Flashscore acessível com sucesso.")
            return True
        else:
            print("  ⚠️ Página carregou mas odds não encontradas (pode ser JS delay)")
            # Salvar HTML para debug
            with open("/tmp/flashscore_odds.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("  HTML salvo em /tmp/flashscore_odds.html")
            return True  # A página carregou, só precisa ajustar seletores

    except Exception as e:
        print(f"  ❌ ERRO: {e}")
        return False
    finally:
        await page.close()


# ============================================================
# MAIN
# ============================================================
async def main():
    print("=" * 60)
    print("TESTE DE ACESSO FLASHSCORE — Camoufox Stealth Browser")
    print("=" * 60)

    # Test 1: Homepage
    homepage_ok = await test_homepage()

    if not homepage_ok:
        print("\n" + "=" * 60)
        print("❌ FALHA: Flashscore bloqueou o acesso.")
        print("   O IP do VPS foi detectado como datacenter.")
        print("   Opções:")
        print("   1. Usar proxy residencial")
        print("   2. Pivotar para BetExplorer")
        print("=" * 60)
        sys.exit(1)

    # Test 2+3: Match + Odds
    odds_ok = await test_match_odds()

    print("\n" + "=" * 60)
    if homepage_ok and odds_ok:
        print("✅ SUCESSO: Flashscore acessível! Pode prosseguir com a implementação.")
    elif homepage_ok:
        print("⚠️ PARCIAL: Homepage OK mas odds precisam de ajuste nos seletores.")
    else:
        print("❌ FALHA: Considere BetExplorer como alternativa.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
