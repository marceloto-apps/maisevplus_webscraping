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
        
        team_resolver = TeamResolver(self._pool)
        await team_resolver.load_cache()
        match_resolver = MatchResolver(self._pool, team_resolver)

        async def process_season(season: dict):
            async with semaphore:
                fs_season_id = season['footystats_season_id']
                data = await self.api_client.fetch_season_matches(fs_season_id)
                
                if data:
                    await self._process_matches_batch(data, season, match_resolver, team_resolver)
                
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
                                     season: dict, 
                                     match_resolver: MatchResolver, 
                                     team_resolver: TeamResolver):
        league_id = season['league_id']
        season_id = season['season_id']
        
        async with self._pool.acquire() as conn:
            for raw_match in matches_data:
                home_name = str(raw_match.get('home_name', ''))
                away_name = str(raw_match.get('away_name', ''))
                
                # Resolução de IDs e captura de pendentes
                home_id = await team_resolver.resolve("footystats", home_name)
                away_id = await team_resolver.resolve("footystats", away_name)

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
                match_id = await match_resolver.resolve_with_footystats(
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
                            home_goal_minutes = $7,
                            away_goal_minutes = $8,
                            updated_at = NOW()
                        WHERE match_id = $9
                        """,
                        fs_id, kickoff, m.get('ft_home'), m.get('ft_away'), m.get('ht_home'), m.get('ht_away'),
                        m.get('home_goal_minutes'), m.get('away_goal_minutes'), match_id
                    )
                else:
                    # INSERT MATCHES
                    m = parsed['matches']
                    match_id = await conn.fetchval(
                        """
                        INSERT INTO matches (
                            season_id, league_id, home_team_id, away_team_id,
                            footystats_id, kickoff, status, ft_home, ft_away, ht_home, ht_away,
                            home_goal_minutes, away_goal_minutes, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, 'finished', $7, $8, $9, $10, $11, $12, NOW())
                        RETURNING match_id
                        """,
                        season_id, league_id, home_id, away_id, fs_id, kickoff,
                        m.get('ft_home'), m.get('ft_away'), m.get('ht_home'), m.get('ht_away'),
                        m.get('home_goal_minutes'), m.get('away_goal_minutes')
                    )

                # INSERT MATC_STATS (Upsert)
                s = parsed['match_stats']
                await conn.execute(
                    """
                    INSERT INTO match_stats (
                        match_id, home_xg, away_xg, home_corners, away_corners,
                        home_yellow, away_yellow, home_red, away_red,
                        home_possession, away_possession, home_shots, away_shots,
                        home_shots_on_target, away_shots_on_target, goal_timing_distribution
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16
                    )
                    ON CONFLICT (match_id) DO UPDATE SET
                        home_xg = EXCLUDED.home_xg,
                        away_xg = EXCLUDED.away_xg,
                        home_corners = EXCLUDED.home_corners,
                        away_corners = EXCLUDED.away_corners,
                        home_yellow = EXCLUDED.home_yellow,
                        away_yellow = EXCLUDED.away_yellow,
                        home_red = EXCLUDED.home_red,
                        away_red = EXCLUDED.away_red,
                        home_possession = EXCLUDED.home_possession,
                        away_possession = EXCLUDED.away_possession,
                        home_shots = EXCLUDED.home_shots,
                        away_shots = EXCLUDED.away_shots,
                        home_shots_on_target = EXCLUDED.home_shots_on_target,
                        away_shots_on_target = EXCLUDED.away_shots_on_target,
                        goal_timing_distribution = EXCLUDED.goal_timing_distribution
                    """,
                    match_id, s.get('home_xg'), s.get('away_xg'), s.get('home_corners'), s.get('away_corners'),
                    s.get('home_yellow'), s.get('away_yellow'), s.get('home_red'), s.get('away_red'),
                    s.get('home_possession'), s.get('away_possession'), s.get('home_shots'), s.get('away_shots'),
                    s.get('home_shots_on_target'), s.get('away_shots_on_target'), s.get('goal_timing_distribution')
                )
