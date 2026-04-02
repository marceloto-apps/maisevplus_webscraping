"""
Parser da página individual de um jogo — mercado 1X2.
Extrai odds de TODAS as bookmakers com opening + closing.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

@dataclass
class BookmakerOdds:
    """Odds de uma bookmaker para um mercado específico."""
    bookmaker: str
    odds_1: Optional[float] = None
    odds_x: Optional[float] = None
    odds_2: Optional[float] = None
    opening_1: Optional[float] = None
    opening_x: Optional[float] = None
    opening_2: Optional[float] = None
    # Para OU/AH
    line: Optional[float] = None
    odds_over: Optional[float] = None
    odds_under: Optional[float] = None
    opening_over: Optional[float] = None
    opening_under: Optional[float] = None
    # Para DC
    odds_1x: Optional[float] = None
    odds_12: Optional[float] = None
    odds_x2: Optional[float] = None
    # Para BTTS
    odds_yes: Optional[float] = None
    odds_no: Optional[float] = None
    # Para DNB
    odds_home: Optional[float] = None
    odds_away: Optional[float] = None

@dataclass
class MatchOddsPage:
    """Resultado do parse de uma página de odds de jogo."""
    match_id: str
    market: str  # "1x2_ft", "ou_ft", etc.
    bookmakers: list[BookmakerOdds] = field(default_factory=list)
    average_odds: Optional[dict] = None
    highest_odds: Optional[dict] = None
    overround: Optional[float] = None
    error: Optional[str] = None

def parse_match_1x2(html: str, match_id: str) -> MatchOddsPage:
    """
    Parse da página 1X2 de um jogo.
    Extrai closing + opening odds de todas as bookmakers.
    """
    soup = BeautifulSoup(html, "html.parser")
    result = MatchOddsPage(match_id=match_id, market="1x2_ft")

    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            bk_name = _extract_bookmaker_name(cells[0])
            if not bk_name:
                continue

            bk = BookmakerOdds(bookmaker=bk_name)

            odds_cells = cells[1:]
            closing = _extract_three_odds(odds_cells)
            if closing:
                bk.odds_1, bk.odds_x, bk.odds_2 = closing

            opening = _extract_opening_odds(odds_cells)
            if opening:
                bk.opening_1, bk.opening_x, bk.opening_2 = opening

            if bk.odds_1 or bk.odds_x or bk.odds_2:
                result.bookmakers.append(bk)

    if result.bookmakers:
        pinnacle = next(
            (b for b in result.bookmakers if "pinnacle" in b.bookmaker.lower()), None
        )
        ref_bk = pinnacle or result.bookmakers[0]
        if ref_bk.odds_1 and ref_bk.odds_x and ref_bk.odds_2:
            result.overround = round(
                (1 / ref_bk.odds_1 + 1 / ref_bk.odds_x + 1 / ref_bk.odds_2 - 1) * 100, 2
            )

    return result

def _extract_bookmaker_name(cell) -> Optional[str]:
    link = cell.find("a")
    if link:
        name = link.get_text(strip=True)
        if name and len(name) > 1:
            return name

    span = cell.find("span")
    if span:
        name = span.get_text(strip=True)
        if name and len(name) > 1:
            return name

    text = cell.get_text(strip=True)
    if text and len(text) > 1 and not re.match(r"^\d", text):
        return text

    return None

def _extract_three_odds(cells: list) -> Optional[tuple[float, float, float]]:
    odds = []
    for cell in cells:
        val = None
        data_odd = cell.get("data-odd")
        if data_odd:
            try: val = float(data_odd)
            except ValueError: pass
        if not val:
            child = cell.find(attrs={"data-odd": True})
            if child:
                try: val = float(child["data-odd"])
                except (ValueError, KeyError): pass
        if not val:
            text = cell.get_text(strip=True)
            match = re.search(r"^\+?(\d+\.\d{2,3})$", text) or re.search(r"(\d+\.\d{2})", text)
            if match: val = float(match.group(1))

        if val is not None:
            odds.append(val)
        if len(odds) == 3:
            return tuple(odds)
    return None

def _extract_opening_odds(cells: list) -> Optional[tuple]:
    openings = []
    for cell in cells:
        val = None
        data_val = cell.get("data-opening-odd")
        if data_val:
            try: val = float(data_val)
            except ValueError: pass

        if not val:
            title = cell.get("title", "")
            opening_match = re.search(r"opening[:\s]+(\d+\.\d{2})", title, re.I)
            if opening_match:
                val = float(opening_match.group(1))

        if not val:
            for attr_name, attr_val in cell.attrs.items():
                if "open" in attr_name.lower():
                    try: 
                        val = float(attr_val)
                        break
                    except (ValueError, TypeError): pass

        if val is not None:
            openings.append(val)
        if len(openings) == 3:
            return tuple(openings)

    # BetExplorer doesn't always have openings on all cells, but we must return something valid
    if len(openings) >= 3:
        return tuple(openings[:3])
    return None
