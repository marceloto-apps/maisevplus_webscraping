"""
Parser da página de resultados/fixtures de uma liga.
Extrai: match_url, match_id, home_team, away_team, score, date, odds_1x2 (se inline).
"""
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .config import BASE_URL

@dataclass
class MatchListItem:
    """Um jogo na lista de resultados/fixtures."""
    match_url: str
    match_id: str
    home_team: str
    away_team: str
    date_str: Optional[str] = None
    score: Optional[str] = None
    status: str = "fixture"     # "fixture" | "finished" | "live"
    odds_1: Optional[float] = None
    odds_x: Optional[float] = None
    odds_2: Optional[float] = None

def parse_results_page(html: str, league_code: str) -> list[MatchListItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    # Encontra links de jogos — padrão: /football/{country}/{league}/{teams}/{match_id}/
    match_links = soup.find_all("a", href=re.compile(r"/football/.+/.+/.+-[a-zA-Z0-9]{6,}/"))
    seen_ids = set()

    for link in match_links:
        href = link.get("href", "")

        match_id_match = re.search(r"/([a-zA-Z0-9]{6,12})/?$", href)
        if not match_id_match:
            continue

        match_id = match_id_match.group(1)
        if match_id in seen_ids:
            continue
        seen_ids.add(match_id)

        team_text = link.get_text(strip=True)
        teams = _parse_teams(team_text, href)
        if not teams:
            continue

        home_team, away_team = teams
        row = link.find_parent("tr")
        odds = _extract_inline_odds(row) if row else (None, None, None)
        score = _extract_score(row) if row else None
        date_str = _extract_date(row, link) if row else None

        item = MatchListItem(
            match_url=urljoin(BASE_URL, href),
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            date_str=date_str,
            score=score,
            status="finished" if score else "fixture",
            odds_1=odds[0],
            odds_x=odds[1],
            odds_2=odds[2],
        )
        items.append(item)

    return items

def _parse_teams(text: str, href: str) -> Optional[tuple[str, str]]:
    if " - " in text:
        parts = text.split(" - ", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()

    slug_match = re.search(r"/football/.+/.+/(.+)/[a-zA-Z0-9]{6,}", href)
    if slug_match:
        slug = slug_match.group(1)
        parts = slug.rsplit("-", 1)
        if len(parts) == 2:
            return parts[0].replace("-", " ").title(), parts[1].replace("-", " ").title()

    return None

def _extract_inline_odds(row) -> tuple[Optional[float], Optional[float], Optional[float]]:
    odds = [None, None, None]
    odd_elements = row.find_all(attrs={"data-odd": True})
    if len(odd_elements) >= 3:
        for i, el in enumerate(odd_elements[:3]):
            try:
                odds[i] = float(el["data-odd"])
            except (ValueError, KeyError):
                pass
        return tuple(odds)

    cells = row.find_all("td")
    decimal_pattern = re.compile(r"^\d+\.\d{2}$")

    odd_values = []
    for cell in cells:
        text = cell.get_text(strip=True)
        if decimal_pattern.match(text):
            try:
                odd_values.append(float(text))
            except ValueError:
                pass

    if len(odd_values) >= 3:
        return (odd_values[0], odd_values[1], odd_values[2])

    return (None, None, None)

def _extract_score(row) -> Optional[str]:
    if not row:
        return None
    score_match = re.search(r"(\d+:\d+)", row.get_text(strip=True))
    return score_match.group(1) if score_match else None

def _extract_date(row, link) -> Optional[str]:
    if not row:
        return None
    date_match = re.search(r"(\d{2}\.\d{2}\.(?:\d{4})?)", row.get_text(strip=True))
    return date_match.group(1) if date_match else None
