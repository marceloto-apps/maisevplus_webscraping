"""
Script de diagnótico rápido da VPS para capturar o HTML de 900KB e inspecionar os modais/classes.
"""
import asyncio
import os
import sys
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.parser import FlashscoreParser, _find_odds_rows
from src.collectors.flashscore.config import FLASHSCORE_BOOKMAKER_MAP
from src.db.logger import configure_logging, get_logger

configure_logging()
logger = get_logger("vps_dump")

async def run_vps_dump(fs_id: str = "E3uvsQPP"):
    dump_dir = os.path.join(os.getcwd(), "scratch", "html_dumps")
    os.makedirs(dump_dir, exist_ok=True)

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()

        url = f"https://www.flashscore.com/match/{fs_id}/"
        logger.info(f"[VPS] Navegando para {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(3000)

        # Inspecionar modais ou botões no DOM inicial
        modals_text = await page.evaluate('''() => {
            let btns = Array.from(document.querySelectorAll('button, a, div[role="dialog"], div[class*="modal"]'));
            return btns.map(b => (b.textContent || '').trim()).filter(t => t.length > 0 && t.length < 50);
        }''')
        logger.info(f"[VPS] Botões/Modais iniciais no DOM ({len(modals_text)}): {modals_text[:15]}")

        # Tentar clicar em qualquer botão com 18 ou Accept ou Consent
        clicked = await page.evaluate('''() => {
            let btns = Array.from(document.querySelectorAll('button, a'));
            let ageBtn = btns.find(b => {
                let txt = (b.textContent || '').trim().toUpperCase();
                return txt.includes('18 AND OLDER') || txt.includes('18+') || txt.includes('MAIOR') || txt.includes('18 ANOS') || txt.includes('I ACCEPT');
            });
            if (ageBtn) {
                ageBtn.click();
                return ageBtn.textContent.trim();
            }
            return false;
        }''')
        logger.info(f"[VPS] Clique em modal inicial: {clicked}")
        await page.wait_for_timeout(1000)

        # Aceitar cookies
        try:
            c = await page.query_selector("#onetrust-accept-btn-handler")
            if c: await c.click()
        except Exception:
            pass

        # Clicar na aba ODDS
        odds_clicked = await page.evaluate('''() => {
            let els = Array.from(document.querySelectorAll('a, button, div[role="tab"]'));
            let target = els.find(l => {
                let href = (l.getAttribute('href') || '').toLowerCase();
                let txt = (l.textContent || '').trim().toUpperCase();
                if (href.includes('legal-age') || href.includes('version') || l.closest('footer')) return false;
                return txt === 'ODDS' || txt === 'COTAÇÕES' || href.includes('/odds-comparison/') || href.includes('/odds/');
            });
            if (target) {
                target.click();
                return target.getAttribute('href') || target.textContent.trim();
            }
            return false;
        }''')
        logger.info(f"[VPS] Clique na aba ODDS: {odds_clicked}")
        await page.wait_for_timeout(4000)

        html = await page.content()
        html_file = os.path.join(dump_dir, f"vps_{fs_id}.html")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"[VPS] HTML salvo em {html_file} ({len(html)} bytes)")

        soup = BeautifulSoup(html, "html.parser")
        rows = _find_odds_rows(soup)
        logger.info(f"[VPS] Linhas da tabela encontradas pelo _find_odds_rows: {len(rows)}")

        entries, stats = FlashscoreParser.parse_odds_table(html, {"sys_market": "1x2", "period": "ft"}, FLASHSCORE_BOOKMAKER_MAP)
        logger.info(f"[VPS] Odds extraídas pelo FlashscoreParser: {len(entries)}")

        if entries:
            print("\n" + "="*80)
            print(f"✅ SUCESSO VPS! EXTRAÍDAS {len(entries)} ODDS:")
            for e in entries:
                print(f"  {e}")
            print("="*80 + "\n")
        else:
            print(f"\nVPS: {len(rows)} rows encontradas, 0 extraídas. Inspecionar HTML {html_file}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fs-id", default="E3uvsQPP")
    args = parser.parse_args()
    asyncio.run(run_vps_dump(args.fs_id))
