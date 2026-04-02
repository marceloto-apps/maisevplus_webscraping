"""
Parser dos mercados secundários (OU, AH, DC, DNB, BTTS).
Recebe o HTML renderizado pelo Playwright e extrai odds estruturadas.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

from .parser_match import BookmakerOdds, MatchOddsPage

def parse_over_under(html: str, match_id: str, period: str = "ft") -> MatchOddsPage:
    market_key = f"ou_{period}"
    soup = BeautifulSoup(html, "html.parser")
    result = MatchOddsPage(match_id=match_id, market=market_key)

    tables = soup.find_all("table")

    for table in tables:
        header = table.find_previous(["h3", "h4", "div", "span"], string=re.compile(r"\d+\.\d"))
        line_match = re.search(r"(\d+\.5)", header.get_text() if header else "")
        line_value = float(line_match.group(1)) if line_match else None

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            bk_name = _get_bk_name(cells[0])
            if not bk_name:
                continue

            bk = BookmakerOdds(bookmaker=bk_name, line=line_value)
            odds_values = _get_two_odds(cells[1:])
            if odds_values:
                bk.odds_over, bk.odds_under = odds_values

            if bk.odds_over or bk.odds_under:
                result.bookmakers.append(bk)

    return result

def parse_asian_handicap(html: str, match_id: str, period: str = "ft") -> MatchOddsPage:
    market_key = f"ah_{period}"
    soup = BeautifulSoup(html, "html.parser")
    result = MatchOddsPage(match_id=match_id, market=market_key)

    tables = soup.find_all("table")

    for table in tables:
        header = table.find_previous(["h3", "h4", "div", "span"], string=re.compile(r"[+-]?\d+\."))
        line_match = re.search(r"([+-]?\d+(?:\.\d+)?)", header.get_text() if header else "")
        line_value = float(line_match.group(1)) if line_match else None

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            bk_name = _get_bk_name(cells[0])
            if not bk_name:
                continue

            bk = BookmakerOdds(bookmaker=bk_name, line=line_value)
            odds_values = _get_two_odds(cells[1:])
            if odds_values:
                bk.odds_1, bk.odds_2 = odds_values

            if bk.odds_1 or bk.odds_2:
                result.bookmakers.append(bk)

    return result

def parse_double_chance(html: str, match_id: str) -> MatchOddsPage:
    soup = BeautifulSoup(html, "html.parser")
    result = MatchOddsPage(match_id=match_id, market="dc_ft")

    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            bk_name = _get_bk_name(cells[0])
            if not bk_name:
                continue

            bk = BookmakerOdds(bookmaker=bk_name)
            three = _get_three_odds(cells[1:])
            if three:
                bk.odds_1x, bk.odds_12, bk.odds_x2 = three

            if bk.odds_1x or bk.odds_12 or bk.odds_x2:
                result.bookmakers.append(bk)

    return result

def parse_draw_no_bet(html: str, match_id: str) -> MatchOddsPage:
    soup = BeautifulSoup(html, "html.parser")
    result = MatchOddsPage(match_id=match_id, market="dnb_ft")

    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            bk_name = _get_bk_name(cells[0])
            if not bk_name:
                continue

            bk = BookmakerOdds(bookmaker=bk_name)
            two = _get_two_odds(cells[1:])
            if two:
                bk.odds_home, bk.odds_away = two

            if bk.odds_home or bk.odds_away:
                result.bookmakers.append(bk)

    return result

def parse_btts(html: str, match_id: str) -> MatchOddsPage:
    soup = BeautifulSoup(html, "html.parser")
    result = MatchOddsPage(match_id=match_id, market="btts_ft")

    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            bk_name = _get_bk_name(cells[0])
            if not bk_name:
                continue

            bk = BookmakerOdds(bookmaker=bk_name)
            two = _get_two_odds(cells[1:])
            if two:
                bk.odds_yes, bk.odds_no = two

            if bk.odds_yes or bk.odds_no:
                result.bookmakers.append(bk)

    return result

def _get_bk_name(cell) -> Optional[str]:
    link = cell.find("a")
    if link:
        name = link.get_text(strip=True)
        if name and len(name) > 1 and not re.match(r"^\d", name):
            return name
    text = cell.get_text(strip=True)
    if text and len(text) > 1 and not re.match(r"^\d", text):
        return text
    return None

def _get_two_odds(cells: list) -> Optional[tuple[float, float]]:
    odds = []
    for cell in cells:
        val = None
        data_odd = cell.get("data-odd")
        if data_odd:
            try: val = float(data_odd)
            except ValueError: pass
        if not val:
            text = cell.get_text(strip=True)
            m = re.search(r"^\+?(\d+\.\d{2,3})$", text) or re.search(r"(\d+\.\d{2})", text)
            if m: val = float(m.group(1))

        if val is not None:
            odds.append(val)
        if len(odds) == 2:
            return (odds[0], odds[1])
    return None

def _get_three_odds(cells: list) -> Optional[tuple]:
    odds = []
    for cell in cells:
        val = None
        data_odd = cell.get("data-odd")
        if data_odd:
            try: val = float(data_odd)
            except ValueError: pass
        if not val:
            text = cell.get_text(strip=True)
            m = re.search(r"^\+?(\d+\.\d{2,3})$", text) or re.search(r"(\d+\.\d{2})", text)
            if m: val = float(m.group(1))

        if val is not None:
            odds.append(val)
        if len(odds) == 3:
            return tuple(odds)
    return None
