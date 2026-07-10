import asyncio
import os
import sys
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.db.pool import get_pool
from src.collectors.flashscore.parser import FlashscoreParser
from src.collectors.flashscore.config import FLASHSCORE_BOOKMAKER_MAP

load_dotenv()

async def main():
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # Pega um match_id e flashscore_id da Premier League (league_id = 1) que falhou no retrofit (no_opening)
        row = await conn.fetchrow("""
            SELECT m.match_id, m.flashscore_id, m.kickoff
            FROM retrofit_match_log l
            JOIN matches m ON l.match_id = m.match_id
            WHERE l.league_id = 1 AND l.status = 'no_opening'
            LIMIT 1
        """)
        
        if not row:
            print("Nenhum match com status 'no_opening' na liga 1 encontrado no log.")
            # Fallback: pega qualquer match da liga 1 com flashscore_id
            row = await conn.fetchrow("""
                SELECT match_id, flashscore_id, kickoff
                FROM matches
                WHERE league_id = 1 AND flashscore_id IS NOT NULL
                LIMIT 1
            """)
            
        if not row:
            print("Nenhuma partida encontrada para a liga 1.")
            return

        flashscore_id = row["flashscore_id"]
        match_id = row["match_id"]
        print(f"Iniciando diagnóstico para match {flashscore_id} (UUID: {match_id})...")

    # Inicia o browser Camoufox
    async with AsyncCamoufox(headless=True) as browser:
        context = await browser.new_context(
            timezone_id="America/Sao_Paulo",
            locale="pt-BR"
        )
        page = await context.new_page()
        
        # 1. Navegar primeiro para a página base
        base_url = f"https://www.flashscore.com/match/{flashscore_id}/"
        print(f"Navegando para base: {base_url}...")
        await page.goto(base_url, wait_until="domcontentloaded", timeout=40000)
        
        # Aceita cookies
        try:
            accept_btn = page.locator('button#onetrust-accept-btn-handler')
            await accept_btn.wait_for(state="visible", timeout=4000)
            await accept_btn.click()
            print("Consentimento de cookies aceito.")
            await page.wait_for_timeout(1000)
        except Exception:
            print("Botão de cookies não apareceu.")

        # 2. Computar a URL real de odds igual em produção
        current_url = page.url
        if "flashscore.com/match/" in current_url:
            base_clean = current_url.split("?")[0].rstrip("/")
            odds_url = f"{base_clean}/odds/1x2-odds/full-time/?mid={flashscore_id}"
        else:
            odds_url = f"https://www.flashscore.com/match/{flashscore_id}/#/odds-comparison/1x2-odds/full-time"
            
        print(f"Navegando para odds real: {odds_url}...")
        await page.goto(odds_url, wait_until="domcontentloaded", timeout=40000)

        # Aguarda a tabela de odds carregar
        selector = "div.ui-table__row, a.oddsCell__odd"
        try:
            await page.wait_for_selector(selector, timeout=15000)
            print("Tabela de odds carregou via selector.")
        except Exception as e:
            print(f"Timeout ao carregar tabela de odds: {e}")
            # Tira um screenshot para diagnóstico
            screenshot_path = "scratch/failed_match_screenshot.png"
            await page.screenshot(path=screenshot_path)
            print(f"Screenshot salvo em {screenshot_path}")
            return

        # Pega o HTML e analisa
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        
        rows = soup.find_all("div", class_="ui-table__row")
        print(f"Total de linhas de odds na tabela: {len(rows)}")
        
        for idx, r in enumerate(rows):
            print(f"\n--- Linha {idx+1} ---")
            # Extrair bookmaker name
            link = r.find('a', href=lambda h: h and '/bookmaker/' in h)
            bm_name = None
            if link:
                bm_name = link.get('title') or link.get_text(strip=True)
            print(f"Bookmaker bruto: {bm_name}")
            
            # Células de odds
            cells = r.find_all("a", class_=lambda c: c and any(x in c.lower() for x in ("oddscell__odd", "oddscellodd")))
            print(f"Total de células de odds encontradas: {len(cells)}")
            for cell_idx, cell in enumerate(cells):
                title = cell.get('title', '') or ''
                span = cell.find("span")
                span_text = span.get_text(strip=True) if span else 'Nenhum'
                print(f"  Cel {cell_idx+1} | span text: '{span_text}' | title: '{title}'")

        # Roda o parser completo para ver o resultado consolidado
        m_config = {"sys_market": "1x2", "period": "ft"}
        results, parsing_stats = FlashscoreParser.parse_odds_table(html, m_config, FLASHSCORE_BOOKMAKER_MAP)
        print("\n=== Resultados do Parser ===")
        print("Parsing Stats:", parsing_stats)
        print("Parsed entries:")
        for res in results:
            print(res)

if __name__ == "__main__":
    asyncio.run(main())
