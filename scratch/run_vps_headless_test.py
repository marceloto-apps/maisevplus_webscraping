"""
Script de teste headless para VPS que utiliza seletores rígidos de <button>
para fechar o modal de idade sem clicar em links do rodapé.
"""
import asyncio
import os
import sys
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.parser import (
    FlashscoreParser,
    _find_odds_rows,
    _find_odds_cells,
    _extract_bookmaker_from_row,
    _extract_cell_odds,
)
from src.collectors.flashscore.config import FLASHSCORE_BOOKMAKER_MAP
from src.db.logger import configure_logging, get_logger

configure_logging()
logger = get_logger("vps_headless")

async def test_vps_headless(fs_id: str = "E3uvsQPP"):
    dump_dir = os.path.join(os.getcwd(), "scratch", "html_dumps")
    os.makedirs(dump_dir, exist_ok=True)

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()

        url = f"https://www.flashscore.com/match/{fs_id}/"
        logger.info(f"[VPS-TEST] Navegando para: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(2000)

        # 1. Clicar no <button> de idade com wait_for
        logger.info("[VPS-TEST] Aguardando possível modal de idade...")
        try:
            btn = page.locator("button:has-text('18 AND OLDER'), button:has-text('18+'), button:has-text('SOU MAIOR')")
            await btn.first.wait_for(state="visible", timeout=6000)
            await btn.first.click()
            logger.info("🎉 [VPS-TEST] <button> de idade clicado com sucesso!")
            await page.wait_for_timeout(1000)
        except Exception:
            logger.info("[VPS-TEST] Nenhum modal de idade surgiu dentro do tempo.")

        # 2. Fechar banner de cookies
        try:
            cookie = page.locator("#onetrust-accept-btn-handler")
            if await cookie.count() > 0:
                await cookie.click()
                logger.info("🎉 [VPS-TEST] Cookie banner fechado!")
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        # 3. Clicar na aba ODDS (garantindo que não é link de rodapé)
        logger.info("[VPS-TEST] Clicando na aba ODDS...")
        odds_clicked = await page.evaluate('''() => {
            let els = Array.from(document.querySelectorAll('a, button, div[role="tab"]'));
            let target = els.find(l => {
                let href = (l.getAttribute('href') || '').toLowerCase();
                let txt = (l.textContent || l.innerText || '').trim().toUpperCase();
                if (href.includes('legal-age') || href.includes('version') || l.closest('footer')) return false;
                return txt === 'ODDS' || txt === 'COTAÇÕES' || href.includes('/odds-comparison/') || href.includes('/odds/');
            });
            if (target) {
                target.click();
                return target.getAttribute('href') || target.textContent.trim();
            }
            return false;
        }''')

        logger.info(f"[VPS-TEST] Resultado do clique em ODDS: {odds_clicked}")

        # 4. Aguardar a tabela de odds carregar no DOM
        try:
            await page.wait_for_selector("div.wclOddsRow, [data-testid='wcl-oddsCell'], button.wcl-oddsCell", timeout=8000)
            logger.info("🎉 [VPS-TEST] Tabela de odds visível no DOM!")
        except Exception as e:
            logger.warning(f"[VPS-TEST] Timeout aguardando tabela de odds: {e}")

        await page.wait_for_timeout(2000)

        # Salvar HTML e Screenshot
        html = await page.content()
        html_file = os.path.join(dump_dir, f"vps_headless_{fs_id}.html")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"[VPS-TEST] HTML salvo em {html_file} ({len(html)} bytes)")

        screenshot_file = os.path.join(dump_dir, f"vps_headless_{fs_id}.png")
        await page.screenshot(path=screenshot_file, full_page=True)
        logger.info(f"[VPS-TEST] Screenshot salvo em {screenshot_file}")

        # Executar FlashscoreParser
        soup = BeautifulSoup(html, "html.parser")
        rows = _find_odds_rows(soup)
        logger.info(f"[VPS-TEST] Linhas encontradas pelo _find_odds_rows: {len(rows)}")

        entries, stats = FlashscoreParser.parse_odds_table(html, {"sys_market": "1x2", "period": "ft"}, FLASHSCORE_BOOKMAKER_MAP)
        logger.info(f"[VPS-TEST] FlashscoreParser extraiu {len(entries)} entradas de odds.")

        if entries:
            print("\n" + "="*80)
            print(f"🎉 SUCESSO TOTAL VPS HEADLESS! EXTRAÍDAS {len(entries)} ODDS PARA MATCH {fs_id}:")
            print("="*80)
            for e in entries:
                print(f"  {e['bookmaker']:<15} | 1: {e['odds_1']} (Open: {e['opening_1']}) | X: {e['odds_x']} (Open: {e['opening_x']}) | 2: {e['odds_2']} (Open: {e['opening_2']})")
            print("="*80 + "\n")
        else:
            print(f"\nResumo VPS Headless: {len(rows)} rows encontradas, 0 extraídas. Inspecionar screenshot {screenshot_file}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fs-id", default="E3uvsQPP")
    args = parser.parse_args()
    asyncio.run(test_vps_headless(args.fs_id))
