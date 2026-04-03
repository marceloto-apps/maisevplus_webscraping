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
                            updated_at = NOW()
                        WHERE match_id = $7
                        """,
                        fs_id, kickoff, m.get('ft_home'), m.get('ft_away'), m.get('ht_home'), m.get('ht_away'),
                        match_id
                    )
                else:
                    # INSERT MATCHES
                    m = parsed['matches']
                    match_id = await conn.fetchval(
                        """
                        INSERT INTO matches (
                            season_id, league_id, home_team_id, away_team_id,
                            footystats_id, kickoff, status, ft_home, ft_away, ht_home, ht_away,
                            updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, 'finished', $7, $8, $9, $10, NOW())
                        RETURNING match_id
                        """,
                        season_id, league_id, home_id, away_id, fs_id, kickoff,
                        m.get('ft_home'), m.get('ft_away'), m.get('ht_home'), m.get('ht_away')
                    )

                # INSERT MATCH_STATS (Upsert)
                # Ordem das colunas segue a migration 011
                s = parsed['match_stats']
                await conn.execute(
                    """
                    INSERT INTO match_stats (
                        match_id,
                        xg_home, xg_away,
                        total_goals_ft,
                        goals_home_minutes, goals_away_minutes,
                        corners_home_ft, corners_away_ft,
                        offsides_home, offsides_away,
                        yellow_cards_home_ft, yellow_cards_away_ft,
                        red_cards_home_ft, red_cards_away_ft,
                        shots_on_target_home, shots_on_target_away,
                        shots_off_target_home, shots_off_target_away,
                        shots_home, shots_away,
                        fouls_home, fouls_away,
                        possession_home, possession_away,
                        btts_potential,
                        corners_home_ht, corners_away_ht,
                        corners_home_2h, corners_away_2h,
                        goals_home_2h, goals_away_2h,
                        cards_home_ht, cards_away_ht,
                        cards_home_2h, cards_away_2h,
                        dangerous_attacks_home, dangerous_attacks_away,
                        attacks_home, attacks_away,
                        goals_home_0_10_min, goals_away_0_10_min,
                        corners_home_0_10_min, corners_away_0_10_min,
                        cards_home_0_10_min, cards_away_0_10_min,
                        home_ppg, away_ppg,
                        pre_match_home_ppg, pre_match_away_ppg,
                        pre_match_overall_ppg_home, pre_match_overall_ppg_away,
                        xg_prematch_home, xg_prematch_away,
                        source
                    ) VALUES (
                        $1,
                        $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                        $21, $22, $23, $24, $25, $26, $27, $28, $29, $30,
                        $31, $32, $33, $34, $35, $36, $37, $38, $39, $40,
                        $41, $42, $43, $44, $45, $46, $47, $48, $49, $50,
                        $51, $52, $53, 'footystats'
                    )
                    ON CONFLICT (match_id, source) DO UPDATE SET
                        xg_home = EXCLUDED.xg_home,
                        xg_away = EXCLUDED.xg_away,
                        total_goals_ft = EXCLUDED.total_goals_ft,
                        goals_home_minutes = EXCLUDED.goals_home_minutes,
                        goals_away_minutes = EXCLUDED.goals_away_minutes,
                        corners_home_ft = EXCLUDED.corners_home_ft,
                        corners_away_ft = EXCLUDED.corners_away_ft,
                        offsides_home = EXCLUDED.offsides_home,
                        offsides_away = EXCLUDED.offsides_away,
                        yellow_cards_home_ft = EXCLUDED.yellow_cards_home_ft,
                        yellow_cards_away_ft = EXCLUDED.yellow_cards_away_ft,
                        red_cards_home_ft = EXCLUDED.red_cards_home_ft,
                        red_cards_away_ft = EXCLUDED.red_cards_away_ft,
                        shots_on_target_home = EXCLUDED.shots_on_target_home,
                        shots_on_target_away = EXCLUDED.shots_on_target_away,
                        shots_off_target_home = EXCLUDED.shots_off_target_home,
                        shots_off_target_away = EXCLUDED.shots_off_target_away,
                        shots_home = EXCLUDED.shots_home,
                        shots_away = EXCLUDED.shots_away,
                        fouls_home = EXCLUDED.fouls_home,
                        fouls_away = EXCLUDED.fouls_away,
                        possession_home = EXCLUDED.possession_home,
                        possession_away = EXCLUDED.possession_away,
                        btts_potential = EXCLUDED.btts_potential,
                        corners_home_ht = EXCLUDED.corners_home_ht,
                        corners_away_ht = EXCLUDED.corners_away_ht,
                        corners_home_2h = EXCLUDED.corners_home_2h,
                        corners_away_2h = EXCLUDED.corners_away_2h,
                        goals_home_2h = EXCLUDED.goals_home_2h,
                        goals_away_2h = EXCLUDED.goals_away_2h,
                        cards_home_ht = EXCLUDED.cards_home_ht,
                        cards_away_ht = EXCLUDED.cards_away_ht,
                        cards_home_2h = EXCLUDED.cards_home_2h,
                        cards_away_2h = EXCLUDED.cards_away_2h,
                        dangerous_attacks_home = EXCLUDED.dangerous_attacks_home,
                        dangerous_attacks_away = EXCLUDED.dangerous_attacks_away,
                        attacks_home = EXCLUDED.attacks_home,
                        attacks_away = EXCLUDED.attacks_away,
                        goals_home_0_10_min = EXCLUDED.goals_home_0_10_min,
                        goals_away_0_10_min = EXCLUDED.goals_away_0_10_min,
                        corners_home_0_10_min = EXCLUDED.corners_home_0_10_min,
                        corners_away_0_10_min = EXCLUDED.corners_away_0_10_min,
                        cards_home_0_10_min = EXCLUDED.cards_home_0_10_min,
                        cards_away_0_10_min = EXCLUDED.cards_away_0_10_min,
                        home_ppg = EXCLUDED.home_ppg,
                        away_ppg = EXCLUDED.away_ppg,
                        pre_match_home_ppg = EXCLUDED.pre_match_home_ppg,
                        pre_match_away_ppg = EXCLUDED.pre_match_away_ppg,
                        pre_match_overall_ppg_home = EXCLUDED.pre_match_overall_ppg_home,
                        pre_match_overall_ppg_away = EXCLUDED.pre_match_overall_ppg_away,
                        xg_prematch_home = EXCLUDED.xg_prematch_home,
                        xg_prematch_away = EXCLUDED.xg_prematch_away
                    """,
                    match_id,
                    s.get('xg_home'), s.get('xg_away'),
                    s.get('total_goals_ft'),
                    s.get('goals_home_minutes'), s.get('goals_away_minutes'),
                    s.get('corners_home_ft'), s.get('corners_away_ft'),
                    s.get('offsides_home'), s.get('offsides_away'),
                    s.get('yellow_cards_home_ft'), s.get('yellow_cards_away_ft'),
                    s.get('red_cards_home_ft'), s.get('red_cards_away_ft'),
                    s.get('shots_on_target_home'), s.get('shots_on_target_away'),
                    s.get('shots_off_target_home'), s.get('shots_off_target_away'),
                    s.get('shots_home'), s.get('shots_away'),
                    s.get('fouls_home'), s.get('fouls_away'),
                    s.get('possession_home'), s.get('possession_away'),
                    s.get('btts_potential'),
                    s.get('corners_home_ht'), s.get('corners_away_ht'),
                    s.get('corners_home_2h'), s.get('corners_away_2h'),
                    s.get('goals_home_2h'), s.get('goals_away_2h'),
                    s.get('cards_home_ht'), s.get('cards_away_ht'),
                    s.get('cards_home_2h'), s.get('cards_away_2h'),
                    s.get('dangerous_attacks_home'), s.get('dangerous_attacks_away'),
                    s.get('attacks_home'), s.get('attacks_away'),
                    s.get('goals_home_0_10_min'), s.get('goals_away_0_10_min'),
                    s.get('corners_home_0_10_min'), s.get('corners_away_0_10_min'),
                    s.get('cards_home_0_10_min'), s.get('cards_away_0_10_min'),
                    s.get('home_ppg'), s.get('away_ppg'),
                    s.get('pre_match_home_ppg'), s.get('pre_match_away_ppg'),
                    s.get('pre_match_overall_ppg_home'), s.get('pre_match_overall_ppg_away'),
                    s.get('xg_prematch_home'), s.get('xg_prematch_away')
                )

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--all-seasons", action="store_true", help="Faz o backfill completo")
    args = parser.parse_args()
    
    from .api_client import FootyStatsClient
    client = FootyStatsClient()
    backfiller = FootyStatsBackfill(client)
    asyncio.run(backfiller.run())
