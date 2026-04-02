"""
Integração do BetExplorer Collector com o scheduler existente.
Define os jobs que o scheduler vai disparar.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from src.collectors.betexplorer.odds_collector import BetExplorerOddsCollector
from src.collectors.betexplorer.config import LEAGUE_BETEXPLORER_PATHS, RateLimitConfig

logger = logging.getLogger(__name__)


# ============================================================
# JOB DEFINITIONS — mapeiam para o scheduler
# ============================================================

async def job_odds_standard(
    league_codes: Optional[list[str]] = None,
    markets: Optional[list[str]] = None,
):
    """
    Job padrão de coleta de odds (fixtures D+1 a D+7).
    Schedule: 6h, 10h, 14h, 20h BRT
    """
    codes = league_codes or list(LEAGUE_BETEXPLORER_PATHS.keys())

    collector = BetExplorerOddsCollector(
        config=RateLimitConfig(),
        markets=markets,  # None = todos os 9 mercados
    )

    all_results = []

    for code in codes:
        try:
            results = await collector.collect_league(
                league_code=code,
                mode="fixtures",
            )
            all_results.extend(results)
            logger.info(f"[odds_standard] {code}: {len(results)} registros")
        except Exception as e:
            logger.error(f"[odds_standard] {code}: ERRO — {e}")

    if all_results:
        inserted = await _insert_odds_batch(all_results)
        logger.info(f"[odds_standard] Total inserido: {inserted}")

    return len(all_results)

async def job_odds_gameday_hourly(
    league_codes: Optional[list[str]] = None,
):
    """
    Job de gameday — coleta horária dos jogos de HOJE.
    Foco em 1X2 + OU + AH (mercados com mais movimento).
    """
    codes = league_codes or list(LEAGUE_BETEXPLORER_PATHS.keys())
    gameday_markets = ["1x2_ft", "ou_ft", "ah_ft"]

    collector = BetExplorerOddsCollector(
        config=RateLimitConfig(
            browser_tab_delay=1.5,
            browser_page_delay=3.0,
        ),
        markets=gameday_markets,
    )

    all_results = []
    for code in codes:
        try:
            results = await collector.collect_league(
                league_code=code,
                mode="fixtures",
            )
            all_results.extend(results)
        except Exception as e:
            logger.error(f"[gameday_hourly] {code}: ERRO — {e}")

    if all_results:
        await _insert_odds_batch(all_results)

    return len(all_results)

async def job_odds_prematch_30(
    match_ids: Optional[list[str]] = None,
):
    """
    Job T-30min: coleta final antes do kickoff.
    Snapshot mais importante para closing line value.
    """
    if not match_ids:
        logger.warning("[prematch_30] Nenhum match_id fornecido")
        return 0

    collector = BetExplorerOddsCollector(
        config=RateLimitConfig(
            browser_tab_delay=1.0,
            browser_wait_after_click=2.0,
        ),
        markets=None,
    )

    logger.info(f"[prematch_30] {len(match_ids)} jogos para coletar")
    return 0

async def job_closing_odds_postmatch(
    league_codes: Optional[list[str]] = None,
):
    """
    Job pós-jogo: coleta closing odds dos jogos encerrados hoje.
    """
    codes = league_codes or list(LEAGUE_BETEXPLORER_PATHS.keys())

    collector = BetExplorerOddsCollector(
        config=RateLimitConfig(),
        markets=None,
    )

    all_results = []
    for code in codes:
        try:
            results = await collector.collect_league(
                league_code=code,
                mode="results",
                max_matches=20,
            )
            for r in results:
                r["is_closing"] = True
            all_results.extend(results)
        except Exception as e:
            logger.error(f"[closing_postmatch] {code}: ERRO — {e}")

    if all_results:
        await _insert_odds_batch(all_results)

    return len(all_results)

# ============================================================
# DATABASE INSERT
# ============================================================

async def _insert_odds_batch(odds_rows: list[dict]) -> int:
    """
    Insere batch de odds no banco.
    TODO: Ligar na engine do SQLAlchemy.
    """
    logger.info(f"  → Inserindo {len(odds_rows)} registros em odds_history...")
    return len(odds_rows)

BETEXPLORER_JOBS = {
    "odds_standard": {
        "function": "src.collectors.betexplorer.scheduler_integration.job_odds_standard",
        "schedule": "0 6,10,14,20 * * *", 
        "args": {},
        "timeout": 3600,
        "description": "Coleta odds BetExplorer — todos os mercados, jogos D+1 a D+7",
    },
    "odds_gameday_hourly": {
        "function": "src.collectors.betexplorer.scheduler_integration.job_odds_gameday_hourly",
        "schedule": "0 8-22 * * *", 
        "condition": "has_games_today",
        "args": {},
        "timeout": 1800,
        "description": "Coleta horária no gameday — 1X2, OU, AH",
    },
    "odds_prematch_30": {
        "function": "src.collectors.betexplorer.scheduler_integration.job_odds_prematch_30",
        "schedule": "dynamic", 
        "args": {"match_ids": "dynamic"},
        "timeout": 600,
        "description": "Snapshot T-30min — todos os mercados",
    },
    "odds_closing_postmatch": {
        "function": "src.collectors.betexplorer.scheduler_integration.job_closing_odds_postmatch",
        "schedule": "0 23 * * *", 
        "args": {},
        "timeout": 3600,
        "description": "Closing odds dos jogos encerrados hoje",
    },
}
