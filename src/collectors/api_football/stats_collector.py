from datetime import datetime, timezone
import json
from src.collectors.base import BaseCollector, CollectResult, CollectStatus
from src.collectors.api_football.client import ApiFootballClient
from src.collectors.api_football.stats_parser import parse_statistics
from src.db.pool import get_pool
from src.db.logger import get_logger

logger = get_logger(__name__)

class StatsCollector(BaseCollector):
    def __init__(self):
        super().__init__("api_football")
        
    async def health_check(self) -> bool:
        return True
        
    async def collect(self, match_id: str, fixture_id: int, team_map: dict) -> CollectResult:
        """
        team_map = { api_football_team_id: db_team_id }
        """
        job_id = self.generate_job_id(f"stats_{match_id}")
        started_at = datetime.now(timezone.utc)
        
        try:
            data = await ApiFootballClient.get("/fixtures/statistics", {"fixture": fixture_id})
            if not data:
                return CollectResult(
                    source=self.source_name, job_type="statistics", job_id=job_id,
                    status=CollectStatus.SUCCESS, started_at=started_at, finished_at=datetime.now(timezone.utc),
                    records=[], records_collected=0, records_new=0
                )
                
            parsed_record = parse_statistics(match_id, data)
            
            pool = await get_pool()
            inserted = 0
            async with pool.acquire() as conn:
                # Um único UPDATE na row respectiva a este match_id
                await conn.execute(
                    """
                    UPDATE match_stats SET
                        shots_off_goal_home = EXCLUDED_COLS.shots_off_goal_home,
                        shots_off_goal_away = EXCLUDED_COLS.shots_off_goal_away,
                        blocked_shots_home = EXCLUDED_COLS.blocked_shots_home,
                        blocked_shots_away = EXCLUDED_COLS.blocked_shots_away,
                        shots_insidebox_home = EXCLUDED_COLS.shots_insidebox_home,
                        shots_insidebox_away = EXCLUDED_COLS.shots_insidebox_away,
                        shots_outsidebox_home = EXCLUDED_COLS.shots_outsidebox_home,
                        shots_outsidebox_away = EXCLUDED_COLS.shots_outsidebox_away,
                        goalkeeper_saves_home = EXCLUDED_COLS.goalkeeper_saves_home,
                        goalkeeper_saves_away = EXCLUDED_COLS.goalkeeper_saves_away,
                        total_passes_home = EXCLUDED_COLS.total_passes_home,
                        total_passes_away = EXCLUDED_COLS.total_passes_away,
                        passes_accurate_home = EXCLUDED_COLS.passes_accurate_home,
                        passes_accurate_away = EXCLUDED_COLS.passes_accurate_away,
                        passes_pct_home = EXCLUDED_COLS.passes_pct_home,
                        passes_pct_away = EXCLUDED_COLS.passes_pct_away,
                        expected_goals_home = EXCLUDED_COLS.expected_goals_home,
                        expected_goals_away = EXCLUDED_COLS.expected_goals_away
                    FROM (VALUES (
                        $2::SMALLINT, $3::SMALLINT, $4::SMALLINT, $5::SMALLINT, 
                        $6::SMALLINT, $7::SMALLINT, $8::SMALLINT, $9::SMALLINT, 
                        $10::SMALLINT, $11::SMALLINT, $12::INTEGER, $13::INTEGER, 
                        $14::INTEGER, $15::INTEGER, $16::NUMERIC, $17::NUMERIC, 
                        $18::NUMERIC, $19::NUMERIC
                    )) AS EXCLUDED_COLS(
                        shots_off_goal_home, shots_off_goal_away, blocked_shots_home, blocked_shots_away,
                        shots_insidebox_home, shots_insidebox_away, shots_outsidebox_home, shots_outsidebox_away,
                        goalkeeper_saves_home, goalkeeper_saves_away, total_passes_home, total_passes_away,
                        passes_accurate_home, passes_accurate_away, passes_pct_home, passes_pct_away,
                        expected_goals_home, expected_goals_away
                    )
                    WHERE match_stats.match_id = $1
                    """,
                    parsed_record.get('match_id'),
                    parsed_record.get('shots_off_goal_home'), parsed_record.get('shots_off_goal_away'),
                    parsed_record.get('blocked_shots_home'), parsed_record.get('blocked_shots_away'),
                    parsed_record.get('shots_insidebox_home'), parsed_record.get('shots_insidebox_away'),
                    parsed_record.get('shots_outsidebox_home'), parsed_record.get('shots_outsidebox_away'),
                    parsed_record.get('goalkeeper_saves_home'), parsed_record.get('goalkeeper_saves_away'),
                    parsed_record.get('total_passes_home'), parsed_record.get('total_passes_away'),
                    parsed_record.get('passes_accurate_home'), parsed_record.get('passes_accurate_away'),
                    parsed_record.get('passes_pct_home'), parsed_record.get('passes_pct_away'),
                    parsed_record.get('expected_goals_home'), parsed_record.get('expected_goals_away')
                )
                inserted = 1
            
            return CollectResult(
                source=self.source_name, job_type="statistics", job_id=job_id,
                status=CollectStatus.SUCCESS, started_at=started_at, finished_at=datetime.now(timezone.utc),
                records=[parsed_record], records_collected=1, records_new=inserted
            )
        except Exception as e:
            logger.error("stats_collector_error", match_id=match_id, error=str(e))
            return CollectResult(
                source=self.source_name, job_type="statistics", job_id=job_id,
                status=CollectStatus.FAILED, started_at=started_at, finished_at=datetime.now(timezone.utc),
                errors=[str(e)], records=[], records_collected=0, records_new=0
            )
