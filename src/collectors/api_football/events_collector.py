from datetime import datetime, timezone
from src.collectors.base import BaseCollector, CollectResult, CollectStatus
from src.collectors.api_football.client import ApiFootballClient
from src.collectors.api_football.events_parser import parse_events
from src.db.pool import get_pool
from src.db.logger import get_logger

logger = get_logger(__name__)

class EventsCollector(BaseCollector):
    def __init__(self):
        super().__init__("api_football")
        
    async def health_check(self) -> bool:
        return True
        
    async def collect(self, match_id: str, fixture_id: int, team_map: dict) -> CollectResult:
        """
        team_map = { api_football_team_id: db_team_id }
        """
        job_id = self.generate_job_id(f"events_{match_id}")
        started_at = datetime.now(timezone.utc)
        
        try:
            data = await ApiFootballClient.get("/fixtures/events", {"fixture": fixture_id})
            if not data:
                return CollectResult(
                    source=self.source_name, job_type="events", job_id=job_id,
                    status=CollectStatus.SUCCESS, started_at=started_at, finished_at=datetime.now(timezone.utc),
                    records=[], records_collected=0, records_new=0
                )
                
            parsed_records = parse_events(match_id, data)
            
            pool = await get_pool()
            inserted = 0
            async with pool.acquire() as conn:
                for rec in parsed_records:
                    db_team_id = team_map.get(rec['team_api_id']) if rec['team_api_id'] else None
                    
                    # Usa INSERT com ON CONFLICT caso o evento ja exista.
                    # Mas match_events tem UNIQUE(match_id, team_id, time_elapsed, time_extra, event_type, player_name)
                    try:
                        await conn.execute(
                            """
                            INSERT INTO match_events 
                            (match_id, time_elapsed, time_extra, team_id, player_id, player_name, assist_id, assist_name, event_type, event_detail, comments)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                            ON CONFLICT DO NOTHING
                            """,
                            match_id,
                            rec['time_elapsed'], rec['time_extra'], db_team_id,
                            rec['player_id'], rec['player_name'],
                            rec['assist_id'], rec['assist_name'],
                            rec['event_type'], rec['event_detail'], rec['comments']
                        )
                        inserted += 1
                    except Exception as ins_err:
                        # Log erro em eventos duvidosos mas continua processando o array
                        logger.warning("events_collector_insert_warning", error=str(ins_err))
            
            return CollectResult(
                source=self.source_name, job_type="events", job_id=job_id,
                status=CollectStatus.SUCCESS, started_at=started_at, finished_at=datetime.now(timezone.utc),
                records=parsed_records, records_collected=len(parsed_records), records_new=inserted
            )
        except Exception as e:
            logger.error("events_collector_error", match_id=match_id, error=str(e))
            return CollectResult(
                source=self.source_name, job_type="events", job_id=job_id,
                status=CollectStatus.FAILED, started_at=started_at, finished_at=datetime.now(timezone.utc),
                errors=[str(e)], records=[], records_collected=0, records_new=0
            )
