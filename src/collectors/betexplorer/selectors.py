"""
Seletores CSS centralizados para o BetExplorer.
"""

RESULTS_PAGE = {
    "main_table": "table.table-main, table[class*='table-main']",
    "match_row": "tr:has(td a[href*='/football/'])",
    "match_link": "a[href*='/football/'][href$='/']",
    "odds_cell": "td[data-odd], td.table-main__odds",
    "date_cell": "td.table-main__date, td:nth-child(last)",
    "score_cell": "td.table-main__result, td:has(span.table-main__result)",
    "round_header": "tr.table-main__head, tr[class*='rtitle']",
}

MATCH_PAGE = {
    "odds_table": "table#sortable-1, table.table-main, table[id*='odds']",
    "bookmaker_row": "tr:has(td a[href*='/bookmaker/'])",
    "bookmaker_name": "td:first-child a, td:first-child span",
    "odds_cells": "td[data-odd], td.table-main__odds",
    "opening_odd_attr": "data-opening-odd",
    "closing_odd_attr": "data-odd",
    "average_row": "tr.average, tr:has-text('Average')",
    "highest_row": "tr.highest, tr:has-text('Highest')",
}

MARKET_TABS_SELECTORS = {
    "over_under": [
        "a[href*='over-under']",
        "li a:has-text('Over/Under')",
        "nav a:has-text('O/U')",
        "[data-market='ou']",
    ],
    "asian_handicap": [
        "a[href*='asian-handicap']",
        "li a:has-text('Asian Handicap')",
        "nav a:has-text('AH')",
        "[data-market='ah']",
    ],
    "double_chance": [
        "a[href*='double-chance']",
        "li a:has-text('Double Chance')",
        "nav a:has-text('DC')",
        "[data-market='dc']",
    ],
    "draw_no_bet": [
        "a[href*='draw-no-bet']",
        "li a:has-text('Draw No Bet')",
        "nav a:has-text('DNB')",
        "[data-market='dnb']",
    ],
    "btts": [
        "a[href*='both-teams']",
        "li a:has-text('Both Teams')",
        "li a:has-text('BTTS')",
        "[data-market='btts']",
    ],
    "first_half": [
        "a[href*='1st-half']",
        "li a:has-text('1st Half')",
        "li a:has-text('First Half')",
        "[data-period='1h']",
    ],
}

ODDS_TABLE = {
    "container": "div#tab-content, div.tab-content, div#odds-content, main",
    "table": "table.table-main, table[class*='sortable'], table[id*='sortable']",
    "header_row": "tr:first-child, thead tr",
    "data_row": "tr:not(:first-child):has(td)",
    "line_header": "h3, h4, div.odds-line, span.odds-line",
}
