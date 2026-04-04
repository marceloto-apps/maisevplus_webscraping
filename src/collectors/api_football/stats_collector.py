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
                
            parsed_records = parse_statistics(match_id, data)
            
            pool = await get_pool()
            inserted = 0
            async with pool.acquire() as conn:
                for rec in parsed_records:
                    db_team_id = team_map.get(rec['team_api_id'])
                    if not db_team_id:
                        continue
                    
                    # Upsert na table match_stats existente 
                    await conn.execute(
                        """
                        INSERT INTO match_stats (match_id, team_id, is_home, stats_json, source)
                        VALUES ($1, $2, (SELECT home_team_id = $2 FROM matches WHERE match_id = $1), $3::jsonb, 'api_football')
                        ON CONFLICT (match_id, team_id, source)
                        DO UPDATE SET stats_json = EXCLUDED.stats_json, updated_at = NOW()
                        """,
                        match_id, db_team_id, rec['stats_json']
                    )
                    inserted += 1
            
            return CollectResult(
                source=self.source_name, job_type="statistics", job_id=job_id,
                status=CollectStatus.SUCCESS, started_at=started_at, finished_at=datetime.now(timezone.utc),
                records=parsed_records, records_collected=len(parsed_records), records_new=inserted
            )
        except Exception as e:
            logger.error("stats_collector_error", match_id=match_id, error=str(e))
            return CollectResult(
                source=self.source_name, job_type="statistics", job_id=job_id,
                status=CollectStatus.FAILED, started_at=started_at, finished_at=datetime.now(timezone.utc),
                error_message=str(e), records=[], records_collected=0, records_new=0
            )
