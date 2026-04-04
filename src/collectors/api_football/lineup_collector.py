from datetime import datetime, timezone
from src.collectors.base import BaseCollector, CollectResult, CollectStatus
from src.collectors.api_football.client import ApiFootballClient
from src.collectors.api_football.lineup_parser import parse_lineups
from src.db.pool import get_pool
from src.db.logger import get_logger

logger = get_logger(__name__)

class LineupCollector(BaseCollector):
    def __init__(self):
        super().__init__("api_football")
        
    async def health_check(self) -> bool:
        return True
        
    async def collect(self, match_id: str, fixture_id: int, team_map: dict) -> CollectResult:
        """
        team_map = { api_football_team_id: db_team_id }
        """
        job_id = self.generate_job_id(f"lineup_{match_id}")
        started_at = datetime.now(timezone.utc)
        
        try:
            data = await ApiFootballClient.get("/fixtures/lineups", {"fixture": fixture_id})
            if not data:
                return CollectResult(
                    source=self.source_name, job_type="lineups", job_id=job_id,
                    status=CollectStatus.SUCCESS, started_at=started_at, finished_at=datetime.now(timezone.utc),
                    records=[], records_collected=0, records_new=0
                )
                
            parsed_records = parse_lineups(match_id, data)
            
            pool = await get_pool()
            inserted = 0
            async with pool.acquire() as conn:
                for rec in parsed_records:
                    db_team_id = team_map.get(rec['team_api_id'])
                    if not db_team_id:
                        continue
                        
                    await conn.execute(
                        """
                        INSERT INTO lineups 
                        (match_id, team_id, is_home, formation, players_json, source)
                        VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                        ON CONFLICT (match_id, team_id, source)
                        DO UPDATE SET
                            formation = EXCLUDED.formation,
                            players_json = EXCLUDED.players_json,
                            is_home = EXCLUDED.is_home,
                            collected_at = NOW()
                        """,
                        match_id, db_team_id, rec['is_home'],
                        rec['formation'], rec['players_json'], rec['source']
                    )
                    inserted += 1
            
            return CollectResult(
                source=self.source_name, job_type="lineups", job_id=job_id,
                status=CollectStatus.SUCCESS, started_at=started_at, finished_at=datetime.now(timezone.utc),
                records=parsed_records, records_collected=len(parsed_records), records_new=inserted
            )
        except Exception as e:
            logger.error("lineup_collector_error", match_id=match_id, error=str(e))
            return CollectResult(
                source=self.source_name, job_type="lineups", job_id=job_id,
                status=CollectStatus.FAILED, started_at=started_at, finished_at=datetime.now(timezone.utc),
                error_message=str(e), records=[], records_collected=0, records_new=0
            )
