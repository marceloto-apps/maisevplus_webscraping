"""
Diagnóstico profundo do pipeline de odds do Flashscore.
Navega para uma partida específica, salva o HTML bruto da página de odds,
e executa o parser localmente para verificar o que é extraído.
"""
import asyncio
import os
import sys
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.parser import FlashscoreParser, _find_odds_rows, _find_odds_cells, _extract_bookmaker_from_row, _extract_cell_odds
from src.db.logger import configure_logging, get_logger
from bs4 import BeautifulSoup

configure_logging()
logger = get_logger("deep_diagnose")


async def diagnose_match(fs_id: str, headless: bool = True):
    """Abre o browser, navega para a partida, salva HTML e diagnostica o parser."""
    
    dump_dir = os.path.join(os.getcwd(), "scratch", "html_dumps")
    os.makedirs(dump_dir, exist_ok=True)
    
    async with AsyncCamoufox(headless=headless) as browser:
        page = await browser.new_page()
        
        # ── PASSO 1: Navegar para a página de odds 1x2 ──
        odds_url = f"https://www.flashscore.com/match/{fs_id}/odds/1x2-odds/full-time/"
        logger.info(f"[DIAG] Navegando para {odds_url}")
        await page.goto(odds_url, wait_until="domcontentloaded", timeout=40000)
        
        # Aceitar cookies se aparecer
        try:
            consent = await page.query_selector("#onetrust-accept-btn-handler")
            if consent:
                await consent.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass
        
        # Aguardar conteúdo renderizar
        await page.wait_for_timeout(5000)
        
        # ── PASSO 2: Salvar HTML bruto ──
        html = await page.content()
        html_path = os.path.join(dump_dir, f"{fs_id}_1x2_ft.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"[DIAG] HTML salvo em {html_path} ({len(html)} bytes)")
        
        # ── PASSO 3: Capturar screenshot ──
        screenshot_path = os.path.join(dump_dir, f"{fs_id}_screenshot.png")
        await page.screenshot(path=screenshot_path, full_page=True)
        logger.info(f"[DIAG] Screenshot salvo em {screenshot_path}")
        
        # ── PASSO 4: Analisar o HTML com BeautifulSoup ──
        soup = BeautifulSoup(html, "html.parser")
        
        # 4a. Verificar se estamos na URL certa
        current_url = page.url
        logger.info(f"[DIAG] URL atual: {current_url}")
        
        # 4b. Buscar TODAS as divs com classe que contenha "odds" (case insensitive)
        all_odds_elements = soup.find_all(
            lambda tag: tag.get("class") and any("odds" in c.lower() for c in tag.get("class"))
        )
        logger.info(f"[DIAG] Total de elementos com 'odds' na classe: {len(all_odds_elements)}")
        
        # 4c. Buscar wclOddsRow especificamente
        wcl_rows = soup.find_all("div", class_=lambda c: c and "wclOddsRow" in " ".join(c) if c else False)
        logger.info(f"[DIAG] Total de div.wclOddsRow: {len(wcl_rows)}")
        
        # 4d. Verificar wcl-oddsCell
        wcl_cells = soup.find_all(lambda tag: tag.get("data-testid") == "wcl-oddsCell")
        logger.info(f"[DIAG] Total de [data-testid='wcl-oddsCell']: {len(wcl_cells)}")
        
        # 4e. Verificar quantas células têm valor numérico vs "-"
        numeric_cells = 0
        dash_cells = 0
        removed_cells = 0
        for cell in wcl_cells:
            val_span = cell.find(lambda tag: tag.get("data-testid") == "wcl-oddsValue")
            if val_span:
                text = val_span.get_text(strip=True)
                if text == "-":
                    dash_cells += 1
                elif text:
                    numeric_cells += 1
            if cell.get("data-removed") == "true":
                removed_cells += 1
        
        logger.info(f"[DIAG] Células com valor numérico: {numeric_cells}")
        logger.info(f"[DIAG] Células com '-' (dash): {dash_cells}")
        logger.info(f"[DIAG] Células com data-removed='true': {removed_cells}")
        
        # 4f. Verificar se existe atributo title com odds de abertura
        cells_with_title = 0
        for cell in wcl_cells:
            for el in [cell] + list(cell.find_all(True)):
                if el.get("title") or el.get("data-title") or el.get("data-tooltip"):
                    cells_with_title += 1
                    title_val = el.get("title") or el.get("data-title") or el.get("data-tooltip")
                    logger.info(f"[DIAG] Encontrado title/tooltip: '{title_val}'")
                    break
        logger.info(f"[DIAG] Células com title/tooltip: {cells_with_title}")
        
        # 4g. Listar todos os data-analytics-bookmaker-id encontrados
        bm_ids = set()
        for cell in wcl_cells:
            bm_id = cell.get("data-analytics-bookmaker-id")
            if bm_id:
                bm_ids.add(bm_id)
        logger.info(f"[DIAG] Bookmaker IDs únicos encontrados: {sorted(bm_ids)}")
        
        # ── PASSO 5: Executar o parser oficial ──
        market_config = {"sys_market": "1x2", "period": "ft"}
        results, stats = FlashscoreParser.parse_odds_table(html, market_config)
        logger.info(f"[DIAG] Parser oficial retornou {len(results)} entradas de odds")
        logger.info(f"[DIAG] Unidentified rows: {stats['unidentified_rows']}")
        logger.info(f"[DIAG] Unknown bookmakers: {stats['unknown_bookmakers']}")
        
        if results:
            for r in results[:3]:
                logger.info(f"[DIAG] Odds: {r}")
        
        # ── PASSO 6: Diagnóstico detalhado row-by-row ──
        rows = _find_odds_rows(soup)
        logger.info(f"[DIAG] _find_odds_rows retornou {len(rows)} rows")
        
        for i, row in enumerate(rows[:5]):
            bm = _extract_bookmaker_from_row(row)
            cells = _find_odds_cells(row)
            
            # Também buscar sem filtrar wcl-empty
            all_cells_raw = row.find_all(lambda tag: tag.get("data-testid") == "wcl-oddsCell")
            
            vals = []
            for cell in cells:
                ct, ov = _extract_cell_odds(cell)
                vals.append({"closing": ct, "opening": ov})
            
            logger.info(
                f"[DIAG] Row {i}: bookmaker={bm} | "
                f"cells_após_filtro={len(cells)} | "
                f"cells_wcl_raw={len(all_cells_raw)} | "
                f"valores={vals}"
            )
        
        # ── RESUMO FINAL ──
        print("\n" + "=" * 80)
        print(f"DIAGNÓSTICO COMPLETO PARA MATCH: {fs_id}")
        print(f"URL: {current_url}")
        print(f"HTML: {len(html)} bytes")
        print(f"Screenshot: {screenshot_path}")
        print(f"wclOddsRow encontradas: {len(wcl_rows)}")
        print(f"wcl-oddsCell encontradas: {len(wcl_cells)}")
        print(f"  - Com valor numérico: {numeric_cells}")
        print(f"  - Com dash '-': {dash_cells}")
        print(f"  - Com data-removed: {removed_cells}")
        print(f"  - Com title/tooltip: {cells_with_title}")
        print(f"Bookmaker IDs: {sorted(bm_ids)}")
        print(f"Parser retornou: {len(results)} entradas de odds")
        print(f"Rows com bookmaker não identificado: {stats['unidentified_rows']}")
        
        if numeric_cells == 0 and dash_cells > 0:
            print("\n⚠️  CONCLUSÃO: Esta partida NÃO tem odds disponíveis no Flashscore.")
            print("   Todas as células mostram '-' (dash) e estão marcadas como 'removed'.")
            print("   O Flashscore removeu os dados de odds para esta partida.")
        elif numeric_cells > 0 and len(results) == 0:
            print("\n🔴 BUG: Existem odds numéricas no HTML mas o parser retornou 0!")
            print("   Investigar _find_odds_cells e _extract_cell_odds.")
        elif len(results) > 0:
            print(f"\n✅ Parser está funcionando! Extraiu {len(results)} entradas de odds.")
        
        print("=" * 80)
        
        await page.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fs-id", required=True, help="Flashscore match ID (ex: E3uvsQPP)")
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()
    
    asyncio.run(diagnose_match(args.fs_id, headless=args.headless))
