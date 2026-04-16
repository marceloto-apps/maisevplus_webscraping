"""Diagnóstico: por que _extract_line_from_cell não acha a célula vazia do handicap 0?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
from src.collectors.flashscore.parser import _extract_line_from_cell, FlashscoreParser
from src.collectors.flashscore.config import FLASHSCORE_BOOKMAKER_MAP

# HTML real observado no DOM do Flashscore para handicap 0
# A célula tem MÚLTIPLAS classes CSS
html_real = """
<html><body>
<div class="ui-table__row" data-testid="wcl-oddsRow">
  <div class="oddsCell__bookmakerPart" data-analytics-bookmaker-id="16" data-analytics-element="ODDS_COMPARISONS_INTERACTIVE_ROW">
    <div class="wcl-bookmakerLogo_4IUU0" data-analytics-bookmaker-id="16" data-analytics-element="ODDS_COMPARIONS_BOOKMAKER_CELL">
      <a href="#" rel="noreferrer" target="_blank" title="bet365">
        <img alt="bet365" class="wcl-logoImage_tPlnM" crossorigin="anonymous" src="https://static.flashscore.com/res/image/data/bookmakers/80-16.png"/>
      </a>
    </div>
    <div class="oddsLiveBetWrapper" data-analytics-bookmaker-id="16">
      <div title="Live Bet"><a class="wcl-badgeLiveBet_8XqLc" href="#" target="_blank"><svg viewbox="1 1 24 20"><title>Live Bet Icon</title></svg></a></div>
    </div>
  </div>
  <div class="ui-table__cell oddsCell__handicap"></div>
  <a class="oddsCell__odd" href="#" target="_blank" title="1.67 to 1.45">
    <span class="">1.45</span>
  </a>
  <a class="oddsCell__odd" href="#" target="_blank" title="2.27 to 2.68">
    <span class="">2.68</span>
  </a>
</div>
</body></html>
"""

soup = BeautifulSoup(html_real, "html.parser")
row = soup.find("div", class_="ui-table__row")

print("=== DIAGNOSTICO ===\n")

# 1. Verificar se find_all("div") encontra a célula
all_divs = row.find_all("div")
print(f"Total de divs na row: {len(all_divs)}")
for i, div in enumerate(all_divs):
    classes = div.get("class", [])
    text = div.get_text(strip=True)
    has_handicap = any("handicap" in c.lower() for c in classes)
    print(f"  div[{i}]: classes={classes}, text='{text[:30]}', has_handicap={has_handicap}")

# 2. Testar o lambda do _extract_line_from_cell
print("\n--- Testando lambda ---")
handicap_cell = row.find(
    lambda tag: tag.name in ("a", "div", "span")
    and tag.get("class")
    and any("handicap" in c.lower() for c in (tag.get("class") or []))
)
print(f"handicap_cell encontrado: {handicap_cell is not None}")
if handicap_cell:
    print(f"  tag: {handicap_cell.name}")
    print(f"  classes: {handicap_cell.get('class')}")
    print(f"  text: '{handicap_cell.get_text(strip=True)}'")
    inner_span = handicap_cell.find("span")
    print(f"  inner_span: {inner_span}")
    raw = (inner_span.get_text(strip=True) if inner_span else handicap_cell.get_text(strip=True))
    print(f"  raw: '{raw}'")
    print(f"  not raw: {not raw}")
else:
    print("  PROBLEMA: lambda nao encontrou a celula handicap!")
    # Debug: vamos tentar uma busca mais simples
    print("\n--- Busca alternativa ---")
    hc2 = row.find("div", class_=lambda c: c and "oddsCell__handicap" in c)
    print(f"  find com string match: {hc2 is not None}")
    if hc2:
        print(f"  classes: {hc2.get('class')}")

# 3. Testar _extract_line_from_cell diretamente
print("\n--- _extract_line_from_cell ---")
result = _extract_line_from_cell(row, signed=True)
print(f"  resultado: {result}")

# 4. Testar parse_odds_table completo
print("\n--- parse_odds_table ---")
config = {"sys_market": "ah", "period": "ft"}
results = FlashscoreParser.parse_odds_table(html_real, config, FLASHSCORE_BOOKMAKER_MAP)
print(f"  registros: {len(results)}")
for r in results:
    print(f"  -> bm={r['bookmaker']}, line={r['line']}, odds1={r['odds_1']}, odds2={r['odds_2']}")
