"""
scratch/debug_1x2_cells.py

Inspeciona o parse do HTML de odds 1x2 para a partida 4ADQOZ24
e verifica por que a odd_1 de abertura foi None ou não foi extraída.
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.parser import FlashscoreParser
from src.collectors.flashscore.config import FLASHSCORE_BOOKMAKER_MAP, MARKETS_CONFIG

async def debug_match():
    async with AsyncCamoufox(headless=True, enable_cache=True) as browser:
        page = await browser.new_page()
        print("[DEBUG] Navegando para 4ADQOZ24...")
        await page.goto("https://www.flashscore.com/match/4ADQOZ24/#/odds-comparison/1x2-odds/full-time", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        # Trata aviso de 18+ se houver
        try:
            btn = page.locator("button:has-text('18')").first
            if await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(1500)
        except Exception:
            pass

        html = await page.content()
        m_config = MARKETS_CONFIG["1x2_ft"]
        results, stats = FlashscoreParser.parse_odds_table(html, m_config, FLASHSCORE_BOOKMAKER_MAP)

        print("\n" + "="*80)
        print(f"RESULTADOS PARSADOS (1x2_ft) ({len(results)} casas):")
        print("="*80)
        for r in results[:10]:
            print(f"Bookmaker: {r['bookmaker']:<15} | Closing: 1={r['odds_1']}, X={r['odds_x']}, 2={r['odds_2']} | Opening: 1={r['opening_1']}, X={r['opening_x']}, 2={r['opening_2']}")
        print("="*80)

if __name__ == "__main__":
    asyncio.run(debug_match())
