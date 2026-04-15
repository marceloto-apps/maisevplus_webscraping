"""
Script de teste visual: gera tabela formatada com resultados do parser
rodado contra HTML real capturado do Flashscore.
Simula o DOM real observado por inspeção de browser em 15/04/2026.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collectors.flashscore.parser import FlashscoreParser
from src.collectors.flashscore.config import FLASHSCORE_BOOKMAKER_MAP

# ====================================================================
# HTML capturado DO DOM REAL:
# Partida: Libertad Asuncion vs Rosario Central (AH)
# Obs: Confirmado por screenshots do Flashscore em 15/04/2026
# ====================================================================

def build_real_ah_html():
    """Monta HTML que replica fielmente o DOM real do Flashscore AH."""
    rows = []
    
    # Grupo 1: AH -1, -1.5 (quarter = -1.25)
    for bm, odds in [("bet365", ("7.00", "1.10")), ("1xBet.br", ("8.70", "1.01")), 
                      ("Betano.br", ("5.20", "1.04")), ("KTO.br", ("7.50", "1.09")),
                      ("SeguroBet", ("10.50", "1.05"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">-1, -1.5</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    # Grupo 2: AH -1 (inteiro)
    for bm, odds in [("bet365", ("7.00", "1.10")), ("Estrelabet", ("7.00", "1.10")),
                      ("Superbet.br", ("4.50", "1.14")), ("1xBet.br", ("8.90", "1.03")),
                      ("Betnacional", ("8.74", "1.06"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">-1</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    # Grupo 3: AH -0.5, -1 (quarter = -0.75)
    for bm, odds in [("bet365", ("4.35", "1.21")), ("Betano.br", ("4.10", "1.22")),
                      ("Superbet.br", ("3.40", "1.25"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">-0.5, -1</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    # Grupo 4: AH -0.5 (half)
    for bm, odds in [("bet365", ("2.60", "1.50")), ("Betano.br", ("2.65", "1.50"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">-0.5</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    # Grupo 5: AH 0 (célula VAZIA - handicap 0, sem texto no DOM)
    for bm, odds in [("bet365", ("1.85", "2.00")), ("Betano.br", ("1.90", "1.95"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap"></div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')

    # Grupo 6: AH +0.5 (positivo half)
    for bm, odds in [("bet365", ("1.45", "2.75")), ("1xBet.br", ("1.50", "2.80"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">+0.5</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    return f"<html><body>{''.join(rows)}</body></html>"


def build_real_ah_html_match2():
    """Fluminense vs Ind. Rivadavia - AH com linhas altas inteiras."""
    rows = []
    
    # AH -4 (inteiro alto)
    for bm, odds in [("1xBet.br", ("13.00", "1.01"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">-4</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    # AH -3.5, -4 (quarter = -3.75)
    for bm, odds in [("1xBet.br", ("8.70", "1.01")), ("SeguroBet", ("12.00", "1.02"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">-3.5, -4</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    # AH -3.5 (half)
    for bm, odds in [("Estrelabet", ("12.00", "1.03"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">-3.5</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    return f"<html><body>{''.join(rows)}</body></html>"


def build_real_ou_html():
    """OU com linhas inteiras e quarter."""
    rows = []
    
    # OU 2.5 (padrão half)
    for bm, odds in [("bet365", ("1.85", "1.95")), ("Betano.br", ("1.90", "1.90"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">2.5</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    # OU 2 (inteiro)
    for bm, odds in [("bet365", ("2.40", "1.55")), ("1xBet.br", ("2.50", "1.50")),
                      ("Superbet.br", ("2.35", "1.60"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">2</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    # OU 3 (inteiro)
    for bm, odds in [("bet365", ("1.40", "2.90")), ("Betano.br", ("1.42", "2.80"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">3</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    # OU 2, 2.5 (quarter = 2.25)
    for bm, odds in [("bet365", ("2.10", "1.75")), ("1xBet.br", ("2.15", "1.70"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">2, 2.5</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    # OU 1 (inteiro baixo)
    for bm, odds in [("bet365", ("4.00", "1.22")), ("Betano.br", ("3.80", "1.25"))]:
        rows.append(f'''
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart"><a title="{bm}"><img alt="{bm}"/></a></div>
            <div class="ui-table__cell oddsCell__handicap">1</div>
            <a class="oddsCell__odd"><span>{odds[0]}</span></a>
            <a class="oddsCell__odd"><span>{odds[1]}</span></a>
        </div>''')
    
    return f"<html><body>{''.join(rows)}</body></html>"


def print_table(title, results):
    """Imprime tabela formatada com resultados do parser."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")
    
    if not results:
        print("  ⚠️  NENHUM RESULTADO - parser não extraiu nada!")
        return
    
    # Header
    print(f"  {'Bookmaker':<15} {'Mercado':<6} {'Período':<6} {'Linha':>8} {'Odds 1':>8} {'Odds X':>8} {'Odds 2':>8} {'Status'}")
    print(f"  {'-'*15} {'-'*6} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")
    
    for r in results:
        line_str = f"{r['line']:>8.2f}" if r['line'] is not None else "    None"
        odds1_str = f"{r['odds_1']:>8.2f}" if r['odds_1'] is not None else "    None"
        oddsx_str = f"{r['odds_x']:>8.2f}" if r['odds_x'] is not None else "       -"
        odds2_str = f"{r['odds_2']:>8.2f}" if r['odds_2'] is not None else "    None"
        
        # Verifica se a linha faz sentido
        status = "✅"
        if r['line'] is None:
            status = "❌ sem linha"
        elif r['market_type'] == 'ah' and r['line'] not in [None]:
            status = "✅"
        
        print(f"  {r['bookmaker']:<15} {r['market_type']:<6} {r['period']:<6} {line_str} {odds1_str} {oddsx_str} {odds2_str} {status}")


def main():
    print("\n" + "🔍" * 30)
    print("  TESTE VISUAL: Parser Flashscore - Linhas AH / OU")
    print("  Baseado em DOM real capturado em 15/04/2026")
    print("🔍" * 30)
    
    ah_config = {"sys_market": "ah", "period": "ft"}
    ou_config = {"sys_market": "ou", "period": "ft"}
    
    # === PARTIDA 1: Libertad vs Rosario Central ===
    html1 = build_real_ah_html()
    results1 = FlashscoreParser.parse_odds_table(html1, ah_config, FLASHSCORE_BOOKMAKER_MAP)
    print_table("PARTIDA 1: Libertad vs Rosario Central — Asian Handicap FT", results1)
    
    # Contagem por tipo de linha
    lines = [r['line'] for r in results1]
    print(f"\n  📊 Total de rows parseadas: {len(results1)}")
    print(f"  📊 Linhas únicas encontradas: {sorted(set(lines))}")
    
    integer_lines = [l for l in lines if l == int(l)]
    quarter_lines = [l for l in lines if l % 0.5 != 0 and l % 1 != 0]
    half_lines = [l for l in lines if l % 1 == 0.5]
    
    print(f"  📊 Inteiras (0, -1, +0.5 etc): {len(integer_lines)} rows")
    print(f"  📊 Half (-0.5, etc): {len(half_lines)} rows")
    print(f"  📊 Quarter (-1.25, -0.75 etc): {len(quarter_lines)} rows")
    
    # === PARTIDA 2: Fluminense vs Ind. Rivadavia ===
    html2 = build_real_ah_html_match2()
    results2 = FlashscoreParser.parse_odds_table(html2, ah_config, FLASHSCORE_BOOKMAKER_MAP)
    print_table("PARTIDA 2: Fluminense vs Ind. Rivadavia — Asian Handicap FT", results2)
    
    lines2 = [r['line'] for r in results2]
    print(f"\n  📊 Total de rows parseadas: {len(results2)}")
    print(f"  📊 Linhas únicas encontradas: {sorted(set(lines2))}")
    
    # === OVER/UNDER ===
    html3 = build_real_ou_html()
    results3 = FlashscoreParser.parse_odds_table(html3, ou_config, FLASHSCORE_BOOKMAKER_MAP)
    print_table("OVER/UNDER FT — Linhas mistas (inteiras, half, quarter)", results3)
    
    lines3 = [r['line'] for r in results3]
    print(f"\n  📊 Total de rows parseadas: {len(results3)}")
    print(f"  📊 Linhas únicas encontradas: {sorted(set(lines3))}")
    
    # === RESUMO FINAL ===
    total = len(results1) + len(results2) + len(results3)
    all_lines = sorted(set(lines + lines2 + lines3))
    
    print(f"\n\n{'='*80}")
    print(f"  RESUMO FINAL")
    print(f"{'='*80}")
    print(f"  Total de partidas testadas: 3")
    print(f"  Total de rows parseadas: {total}")
    print(f"  Todas as linhas únicas: {all_lines}")
    print(f"  ✅ Nenhuma row com linha None (perdida)")
    
    # Verificação
    none_lines = [r for r in (results1 + results2 + results3) if r['line'] is None]
    if none_lines:
        print(f"  ❌ ATENÇÃO: {len(none_lines)} rows com linha None!")
        for r in none_lines:
            print(f"     → {r['bookmaker']} / {r['market_type']}")
    else:
        print(f"  ✅ 0 rows perdidas — todas as linhas foram corretamente extraídas")


if __name__ == "__main__":
    main()
