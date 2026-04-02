"""
T06 — Footystats Backfill Script
Realiza dump histórico completo baixando seasons inteiras via API.
"""
import asyncio
import csv
import os
from typing import List, Dict

from ...db import get_pool
from ...db.logger import get_logger
from .api_client import FootyStatsClient
from .matches_collector import MatchesCollector
from ...normalizer.team_resolver import TeamResolver, MatchResolver

logger = get_logger(__name__)

CONCURRENCY = 5
DELAY_BETWEEN = 0.5

class FootyStatsBackfill:
    def __init__(self, api_client: FootyStatsClient):
        self.api_client = api_client
        self._pool = None
        self.unresolved_teams = set()

    async def _init_db(self):
        if self._pool is None:
            self._pool = await get_pool()

    async def run(self, output_pending: str = "output/footystats_unresolved_teams.csv"):
        await self._init_db()

        async with self._pool.acquire() as conn:
            seasons = await conn.fetch(
                """
                SELECT season_id, league_id, footystats_season_id 
                FROM seasons
                WHERE footystats_season_id IS NOT NULL
                """
            )

        logger.info("footystats_backfill_start", seasons_count=len(seasons))

        semaphore = asyncio.Semaphore(CONCURRENCY)
        
        await TeamResolver.load_cache()

        async def process_season(season: dict):
            async with semaphore:
                fs_season_id = season['footystats_season_id']
                data = await self.api_client.fetch_season_matches(fs_season_id)
                
                if data:
                    await self._process_matches_batch(data, season)
                
                await asyncio.sleep(DELAY_BETWEEN)
        
        await asyncio.gather(*[process_season(s) for s in seasons])
        
        # Export unresolved teams
        if self.unresolved_teams:
            os.makedirs(os.path.dirname(output_pending), exist_ok=True)
            with open(output_pending, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["raw_name"])
                for team in sorted(list(self.unresolved_teams)):
                    writer.writerow([team])
            logger.warning("unresolved_teams_exported", count=len(self.unresolved_teams), path=output_pending)

        logger.info("footystats_backfill_done")

    async def _process_matches_batch(self, 
                                     matches_data: List[Dict], 
                                     season: dict):
        league_id = season['league_id']
        season_id = season['season_id']
        
        async with self._pool.acquire() as conn:
            for raw_match in matches_data:
                home_name = str(raw_match.get('home_name', ''))
                away_name = str(raw_match.get('away_name', ''))
                
                # Resolução de IDs e captura de pendentes
                home_id = await TeamResolver.resolve("footystats", home_name)
                away_id = await TeamResolver.resolve("footystats", away_name)

                if home_id is None:
                    self.unresolved_teams.add(home_name)
                if away_id is None:
                    self.unresolved_teams.add(away_name)
                if home_id is None or away_id is None:
                    continue  # Pula! Requer revisao de aliases.

                fs_id = raw_match.get('id')
                parsed = MatchesCollector.parse_raw_match(raw_match)
                kickoff = parsed['matches'].get('kickoff')
                
                if not fs_id or not kickoff:
                    continue

                # O MATCH RESOLVER:
                # Prioridade 1, 2, 3 com lock de 1-dia
                match_id = await MatchResolver.resolve_with_footystats(
                    league_id, home_name, away_name, kickoff.date(), fs_id
                )

                if match_id:
                    # UPDATE MATCHES
                    m = parsed['matches']
                    await conn.execute(
                        """
                        UPDATE matches SET
                            footystats_id = $1,
                            kickoff = $2,
                            status = 'finished',
                            ft_home = $3,
                            ft_away = $4,
                            ht_home = $5,
                            ht_away = $6,
                            goals_home_minutes = $7,
                            goals_away_minutes = $8,
                            updated_at = NOW()
                        WHERE match_id = $9
                        """,
                        fs_id, kickoff, m.get('ft_home'), m.get('ft_away'), m.get('ht_home'), m.get('ht_away'),
                        m.get('goals_home_minutes'), m.get('goals_away_minutes'), match_id
                    )
                else:
                    # INSERT MATCHES
                    m = parsed['matches']
                    match_id = await conn.fetchval(
                        """
                        INSERT INTO matches (
                            season_id, league_id, home_team_id, away_team_id,
                            footystats_id, kickoff, status, ft_home, ft_away, ht_home, ht_away,
                            goals_home_minutes, goals_away_minutes, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, 'finished', $7, $8, $9, $10, $11, $12, NOW())
                        RETURNING match_id
                        """,
                        season_id, league_id, home_id, away_id, fs_id, kickoff,
                        m.get('ft_home'), m.get('ft_away'), m.get('ht_home'), m.get('ht_away'),
                        m.get('goals_home_minutes'), m.get('goals_away_minutes')
                    )

                # INSERT MATCH_STATS (Upsert)
                s = parsed['match_stats']
                await conn.execute(
                    """
                    INSERT INTO match_stats (
                        match_id, source, xg_home, xg_away, corners_home_ft, corners_away_ft,
                        yellow_cards_home_ft, yellow_cards_away_ft, red_cards_home_ft, red_cards_away_ft,
                        possession_home, possession_away, shots_home, shots_away,
                        shots_on_target_home, shots_on_target_away
                    ) VALUES (
                        $1, 'footystats', $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
                    )
                    ON CONFLICT (match_id, source) DO UPDATE SET
                        xg_home = EXCLUDED.xg_home,
                        xg_away = EXCLUDED.xg_away,
                        corners_home_ft = EXCLUDED.corners_home_ft,
                        corners_away_ft = EXCLUDED.corners_away_ft,
                        yellow_cards_home_ft = EXCLUDED.yellow_cards_home_ft,
                        yellow_cards_away_ft = EXCLUDED.yellow_cards_away_ft,
                        red_cards_home_ft = EXCLUDED.red_cards_home_ft,
                        red_cards_away_ft = EXCLUDED.red_cards_away_ft,
                        possession_home = EXCLUDED.possession_home,
                        possession_away = EXCLUDED.possession_away,
                        shots_home = EXCLUDED.shots_home,
                        shots_away = EXCLUDED.shots_away,
                        shots_on_target_home = EXCLUDED.shots_on_target_home,
                        shots_on_target_away = EXCLUDED.shots_on_target_away
                    """,
                    match_id, s.get('xg_home'), s.get('xg_away'), s.get('corners_home_ft'), s.get('corners_away_ft'),
                    s.get('yellow_cards_home_ft'), s.get('yellow_cards_away_ft'), s.get('red_cards_home_ft'), s.get('red_cards_away_ft'),
                    s.get('possession_home'), s.get('possession_away'), s.get('shots_home'), s.get('shots_away'),
                    s.get('shots_on_target_home'), s.get('shots_on_target_away')
                )
