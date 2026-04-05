from datetime import datetime, timezone
from src.collectors.base import BaseCollector, CollectResult, CollectStatus
from src.collectors.api_football.client import ApiFootballClient
from src.collectors.api_football.players_parser import parse_players
from src.db.pool import get_pool
from src.db.logger import get_logger

logger = get_logger(__name__)

class PlayersCollector(BaseCollector):
    def __init__(self):
        super().__init__("api_football")
        
    async def health_check(self) -> bool:
        return True
        
    async def collect(self, match_id: str, fixture_id: int, team_map: dict) -> CollectResult:
        """
        team_map = { api_football_team_id: db_team_id }
        """
        job_id = self.generate_job_id(f"players_{match_id}")
        started_at = datetime.now(timezone.utc)
        
        try:
            data = await ApiFootballClient.get("/fixtures/players", {"fixture": fixture_id})
            if not data:
                return CollectResult(
                    source=self.source_name, job_type="players", job_id=job_id,
                    status=CollectStatus.SUCCESS, started_at=started_at, finished_at=datetime.now(timezone.utc),
                    records=[], records_collected=0, records_new=0
                )
                
            parsed_records = parse_players(match_id, data)
            
            pool = await get_pool()
            inserted = 0
            async with pool.acquire() as conn:
                for rec in parsed_records:
                    db_team_id = team_map.get(rec['team_api_id'])
                    if not db_team_id:
                        continue
                        
                    await conn.execute(
                        """
                        INSERT INTO match_player_stats 
                        (match_id, team_id, player_id, player_name, minutes_played, rating,
                         goals, assists, shots_total, shots_on, passes_total, passes_key, passes_accuracy,
                         tackles, blocks, interceptions, duels_total, duels_won, dribbles_attempts, dribbles_success,
                         fouls_drawn, fouls_committed, cards_yellow, cards_red, offsides, saves)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26)
                        ON CONFLICT (match_id, player_id) DO UPDATE SET
                            minutes_played=EXCLUDED.minutes_played, rating=EXCLUDED.rating, goals=EXCLUDED.goals, assists=EXCLUDED.assists,
                            shots_total=EXCLUDED.shots_total, shots_on=EXCLUDED.shots_on, passes_total=EXCLUDED.passes_total,
                            passes_key=EXCLUDED.passes_key, passes_accuracy=EXCLUDED.passes_accuracy, tackles=EXCLUDED.tackles,
                            blocks=EXCLUDED.blocks, interceptions=EXCLUDED.interceptions, duels_total=EXCLUDED.duels_total,
                            duels_won=EXCLUDED.duels_won, dribbles_attempts=EXCLUDED.dribbles_attempts, dribbles_success=EXCLUDED.dribbles_success,
                            fouls_drawn=EXCLUDED.fouls_drawn, fouls_committed=EXCLUDED.fouls_committed, cards_yellow=EXCLUDED.cards_yellow,
                            cards_red=EXCLUDED.cards_red, offsides=EXCLUDED.offsides, saves=EXCLUDED.saves
                        """,
                        match_id, db_team_id, rec['player_id'], rec['player_name'], rec['minutes_played'], rec['rating'],
                        rec['goals'], rec['assists'], rec['shots_total'], rec['shots_on'], rec['passes_total'], rec['passes_key'], rec['passes_accuracy'],
                        rec['tackles'], rec['blocks'], rec['interceptions'], rec['duels_total'], rec['duels_won'], rec['dribbles_attempts'], rec['dribbles_success'],
                        rec['fouls_drawn'], rec['fouls_committed'], rec['cards_yellow'], rec['cards_red'], rec['offsides'], rec['saves']
                    )
                    inserted += 1
            
            return CollectResult(
                source=self.source_name, job_type="players", job_id=job_id,
                status=CollectStatus.SUCCESS, started_at=started_at, finished_at=datetime.now(timezone.utc),
                records=parsed_records, records_collected=len(parsed_records), records_new=inserted
            )
        except Exception as e:
            logger.error("players_collector_error", match_id=match_id, error=str(e))
            return CollectResult(
                source=self.source_name, job_type="players", job_id=job_id,
                status=CollectStatus.FAILED, started_at=started_at, finished_at=datetime.now(timezone.utc),
                errors=[str(e)], records=[], records_collected=0, records_new=0
            )
