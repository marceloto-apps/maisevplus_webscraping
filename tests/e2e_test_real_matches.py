"""
Teste E2E real: captura odds de 3 partidas reais do Flashscore
usando o browser e roda o parser corrigido.
Resultados salvos em CSV para validação manual.

Partidas:
- bZOttMQ7
- tIQAG22K
- 27VXsrde

Mercados: 1x2 FT, Over/Under FT, Asian Handicap FT, BTTS FT
"""
import asyncio
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.parser import FlashscoreParser
from src.collectors.flashscore.config import FLASHSCORE_BOOKMAKER_MAP

# Partidas de teste
MATCH_IDS = ["bZOttMQ7", "tIQAG22K", "27VXsrde"]

# Mercados a coletar (ordem de navegação)
MARKETS = [
    {"key": "1x2_ft", "sys_market": "1x2", "period": "ft", "tab_slug": None,          "label": "1X2"},
    {"key": "ou_ft",  "sys_market": "ou",  "period": "ft", "tab_slug": "over-under",   "label": "Over/Under"},
    {"key": "ah_ft",  "sys_market": "ah",  "period": "ft", "tab_slug": "asian-handicap","label": "Asian Handicap"},
    {"key": "btts",   "sys_market": "btts","period": "ft", "tab_slug": "both-teams-to-score", "label": "BTTS"},
]

OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultado_teste_e2e.csv")


async def capture_match(browser, match_id: str) -> list[dict]:
    """Captura odds de todos os mercados para uma partida."""
    all_results = []
    page = await browser.new_page()
    
    try:
        # 1. Navegar para a página da partida
        base_url = f"https://www.flashscore.com/match/{match_id}/"
        print(f"\n{'='*70}")
        print(f"  PARTIDA: {match_id}")
        print(f"  URL: {base_url}")
        print(f"{'='*70}")
        
        await page.goto(base_url, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(2000)
        
        # Capturar nome dos times
        try:
            home_el = await page.query_selector(".duelParticipant__home .participant__participantName")
            away_el = await page.query_selector(".duelParticipant__away .participant__participantName")
            home_name = await home_el.inner_text() if home_el else "?"
            away_name = await away_el.inner_text() if away_el else "?"
            print(f"  JOGO: {home_name} vs {away_name}")
        except Exception:
            home_name, away_name = "?", "?"
            print(f"  JOGO: (nao conseguiu capturar nomes)")
        
        # Fechar cookie banner se existir
        try:
            accept_btn = page.locator('button#onetrust-accept-btn-handler')
            if await accept_btn.count() > 0:
                await accept_btn.click(timeout=3000)
                await page.wait_for_timeout(500)
        except Exception:
            pass
        
        # 2. Clicar na aba ODDS
        try:
            await page.wait_for_selector("a[href*='/odds/']", timeout=10000)
            odds_tab = await page.query_selector("a[href*='/odds/']")
            if odds_tab:
                await odds_tab.click()
                await page.wait_for_timeout(2000)
            else:
                print("  ERRO: Aba Odds nao encontrada")
                return all_results
        except Exception as e:
            print(f"  ERRO na aba Odds: {e}")
            return all_results
        
        # Esperar tabela renderizar
        try:
            await page.wait_for_selector("div.ui-table__row", timeout=10000)
        except Exception:
            try:
                await page.wait_for_selector("a.oddsCell__odd", timeout=5000)
            except Exception:
                print("  AVISO: Tabela de odds nao renderizou")
        
        # 3. Iterar pelos mercados
        is_first = True
        for mkt in MARKETS:
            print(f"\n  [{mkt['label']}]", end=" ")
            
            try:
                if not is_first and mkt["tab_slug"]:
                    # Clicar na sub-aba do mercado
                    tab = await page.query_selector(f"a[href*='/{mkt['tab_slug']}/']")
                    if not tab:
                        # Tentar pelo texto
                        tab = await page.query_selector(f"button:has-text('{mkt['label']}')")
                    
                    if not tab:
                        print(f"-> Sub-aba nao encontrada, pulando")
                        continue
                    
                    await tab.click()
                    await page.wait_for_timeout(2000)
                    
                    # Esperar tabela re-renderizar    
                    try:
                        await page.wait_for_selector("div.ui-table__row", timeout=8000)
                    except Exception:
                        await page.wait_for_timeout(2000)
                
                is_first = False
                
                # Capturar HTML e parsear
                html = await page.content()
                market_config = {"sys_market": mkt["sys_market"], "period": mkt["period"]}
                entries = FlashscoreParser.parse_odds_table(html, market_config, FLASHSCORE_BOOKMAKER_MAP)
                
                print(f"-> {len(entries)} registros capturados")
                
                for entry in entries:
                    entry["flashscore_id"] = match_id
                    entry["match_label"] = f"{home_name} vs {away_name}"
                    entry["market_key"] = mkt["key"]
                    all_results.append(entry)
                    
            except Exception as e:
                print(f"-> ERRO: {e}")
                is_first = False
    
    finally:
        await page.close()
    
    return all_results


async def main():
    print("\n" + "=" * 70)
    print("  TESTE E2E: Flashscore Parser - Captura Real")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Partidas: {', '.join(MATCH_IDS)}")
    print(f"  Mercados: 1x2, OU, AH, BTTS (todos FT)")
    print("=" * 70)
    
    all_results = []
    
    async with AsyncCamoufox(headless=False) as browser:
        for match_id in MATCH_IDS:
            results = await capture_match(browser, match_id)
            all_results.extend(results)
            await asyncio.sleep(2)  # Intervalo entre partidas
    
    # Salvar CSV
    if all_results:
        fieldnames = ["flashscore_id", "match_label", "market_key", "market_type", 
                      "period", "bookmaker", "line", "odds_1", "odds_x", "odds_2"]
        
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            for r in all_results:
                writer.writerow({k: r.get(k, "") for k in fieldnames})
        
        print(f"\n\n{'='*70}")
        print(f"  RESULTADO FINAL")
        print(f"{'='*70}")
        print(f"  Total de registros: {len(all_results)}")
        print(f"  CSV salvo em: {OUTPUT_CSV}")
        
        # Resumo por partida e mercado
        from collections import Counter
        by_match_market = Counter((r["flashscore_id"], r["market_key"]) for r in all_results)
        
        print(f"\n  {'Partida':<12} {'Mercado':<10} {'Registros':>10}")
        print(f"  {'-'*12} {'-'*10} {'-'*10}")
        for (mid, mkt), count in sorted(by_match_market.items()):
            print(f"  {mid:<12} {mkt:<10} {count:>10}")
        
        # Resumo de linhas AH/OU
        ah_lines = sorted(set(r["line"] for r in all_results if r["market_type"] == "ah" and r["line"] is not None))
        ou_lines = sorted(set(r["line"] for r in all_results if r["market_type"] == "ou" and r["line"] is not None))
        
        if ah_lines:
            print(f"\n  Linhas AH encontradas: {ah_lines}")
        if ou_lines:
            print(f"  Linhas OU encontradas: {ou_lines}")
        
        # Tabela detalhada
        print(f"\n  {'='*90}")
        print(f"  DETALHAMENTO COMPLETO")
        print(f"  {'='*90}")
        print(f"  {'ID':<10} {'BM':<14} {'Mercado':<6} {'Linha':>7} {'Odds1':>7} {'OddsX':>7} {'Odds2':>7}")
        print(f"  {'-'*10} {'-'*14} {'-'*6} {'-'*7} {'-'*7} {'-'*7} {'-'*7}")
        
        for r in all_results:
            line_s = f"{r['line']:>7.2f}" if r['line'] is not None else "      -"
            o1 = f"{r['odds_1']:>7.2f}" if r['odds_1'] is not None else "      -"
            ox = f"{r['odds_x']:>7.2f}" if r['odds_x'] is not None else "      -"
            o2 = f"{r['odds_2']:>7.2f}" if r['odds_2'] is not None else "      -"
            print(f"  {r['flashscore_id']:<10} {r['bookmaker']:<14} {r['market_type']:<6} {line_s} {o1} {ox} {o2}")
    else:
        print("\n  NENHUM RESULTADO capturado!")


if __name__ == "__main__":
    asyncio.run(main())
