"""
Orquestrador principal do BetExplorer Odds Collector.
Coordena Engine A (httpx) e Engine B (Playwright) para cobertura completa.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from .config import (
    BASE_URL,
    LEAGUE_BETEXPLORER_PATHS,
    MARKET_TABS,
    RateLimitConfig,
)
from .client_http import BetExplorerHttpClient
from .client_browser import BetExplorerBrowserClient
from .parser_results import parse_results_page, MatchListItem
from .parser_match import parse_match_1x2, MatchOddsPage
from .parser_markets import (
    parse_over_under,
    parse_asian_handicap,
    parse_double_chance,
    parse_draw_no_bet,
    parse_btts,
)
from .url_builder import build_results_url, build_fixtures_url

logger = logging.getLogger(__name__)

class BetExplorerOddsCollector:
    """
    Coletor principal de odds do BetExplorer.
    """

    def __init__(
        self,
        config: Optional[RateLimitConfig] = None,
        markets: Optional[list[str]] = None,
    ):
        self.config = config or RateLimitConfig()
        self.http_client = BetExplorerHttpClient(self.config)

        self.markets = markets or list(MARKET_TABS.keys())
        self.http_markets = [m for m in self.markets if MARKET_TABS.get(m, {}).get("engine") == "httpx"]
        self.browser_markets = [m for m in self.markets if MARKET_TABS.get(m, {}).get("engine") == "playwright"]
        self._browser_client: Optional[BetExplorerBrowserClient] = None

    async def collect_league(
        self,
        league_code: str,
        mode: str = "fixtures",
        max_matches: Optional[int] = None,
    ) -> list[dict]:
        slug = LEAGUE_BETEXPLORER_PATHS.get(league_code)
        if not slug:
            logger.error(f"Liga {league_code} não mapeada no BetExplorer")
            return []

        url = build_fixtures_url(slug) if mode == "fixtures" else build_results_url(slug)
        logger.info(f"Coletando {mode} de {league_code}: {url}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            status, html = await self.http_client.get(url, client)

        if status != 200:
            logger.error(f"Falha ao carregar {url}: HTTP {status}")
            return []

        matches = parse_results_page(html, league_code)
        if max_matches:
            matches = matches[:max_matches]

        logger.info(f"  {len(matches)} jogos encontrados em {league_code}")

        all_odds = []

        for i, match in enumerate(matches):
            logger.info(f"  [{i+1}/{len(matches)}] {match.home_team} vs {match.away_team}")
            match_odds = await self._collect_single_match(match)
            all_odds.extend(match_odds)

            if self.browser_markets:
                await asyncio.sleep(self.config.browser_page_delay)

        logger.info(f"  Total: {len(all_odds)} registros de odds coletados para {league_code}")
        return all_odds

    async def _collect_single_match(self, match: MatchListItem) -> list[dict]:
        results = []

        # Engine A foi restringida apenas para a Listagem (Fixtures/Results).
        # Todos os mercados (inclusos 1x2) vão cair na Engine B.

        # Engine B
        if self.browser_markets:
            if not self._browser_client:
                self._browser_client = BetExplorerBrowserClient(self.config)

            market_htmls = await self._browser_client.extract_match_markets(
                match.match_url, self.browser_markets
            )

            for market_key, market_html in market_htmls.items():
                if market_key.startswith("_"):
                    continue

                odds_page = self._parse_market_html(
                    market_key, market_html, match.match_id
                )
                if odds_page:
                    results.extend(self._normalize_odds_page(odds_page, match))

        return results

    def _parse_market_html(
        self, market_key: str, html: str, match_id: str
    ) -> Optional[MatchOddsPage]:
        parsers = {
            "1x2_ft": lambda h, m: parse_match_1x2(h, m),
            "ou_ft": lambda h, m: parse_over_under(h, m, "ft"),
            "ou_ht": lambda h, m: parse_over_under(h, m, "ht"),
            "ah_ft": lambda h, m: parse_asian_handicap(h, m, "ft"),
            "ah_ht": lambda h, m: parse_asian_handicap(h, m, "ht"),
            "dc_ft": parse_double_chance,
            "dnb_ft": parse_draw_no_bet,
            "btts_ft": parse_btts,
            "1x2_ht": lambda h, m: parse_match_1x2(h, m),
        }

        parser = parsers.get(market_key)
        if parser:
            try:
                return parser(html, match_id)
            except Exception as e:
                logger.warning(f"Erro no parse de {market_key}: {e}")
        return None

    def _normalize_odds_page(
        self, odds_page: MatchOddsPage, match: MatchListItem
    ) -> list[dict]:
        rows = []
        timestamp = datetime.now(timezone.utc).isoformat()

        for bk in odds_page.bookmakers:
            row = {
                "match_id": match.match_id,
                "source": "betexplorer",
                "market": odds_page.market,
                "bookmaker": bk.bookmaker,
                "home_team": match.home_team,
                "away_team": match.away_team,
                "collected_at": timestamp,
                "is_opening": False,
                "is_closing": match.status == "finished",
            }

            if odds_page.market.startswith("1x2"):
                row.update({
                    "odds_1": bk.odds_1,
                    "odds_x": bk.odds_x,
                    "odds_2": bk.odds_2,
                    "opening_1": bk.opening_1,
                    "opening_x": bk.opening_x,
                    "opening_2": bk.opening_2,
                })
            elif odds_page.market.startswith("ou"):
                row.update({
                    "line": bk.line,
                    "odds_over": bk.odds_over,
                    "odds_under": bk.odds_under,
                })
            elif odds_page.market.startswith("ah"):
                row.update({
                    "line": bk.line,
                    "odds_home": bk.odds_1,
                    "odds_away": bk.odds_2,
                })
            elif odds_page.market == "dc_ft":
                row.update({
                    "odds_1x": bk.odds_1x,
                    "odds_12": bk.odds_12,
                    "odds_x2": bk.odds_x2,
                })
            elif odds_page.market == "dnb_ft":
                row.update({
                    "odds_home": bk.odds_home,
                    "odds_away": bk.odds_away,
                })
            elif odds_page.market == "btts_ft":
                row.update({
                    "odds_yes": bk.odds_yes,
                    "odds_no": bk.odds_no,
                })

            rows.append(row)

        return rows
