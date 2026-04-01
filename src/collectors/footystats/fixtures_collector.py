"""
T06 — Fixtures Collector
Coleta os jogos das próximas rodadas (futuro).
Lida com a inclusão de jogos agendados com status='scheduled'.
"""
import asyncio
from datetime import datetime, timezone
from typing import List

from ...db import get_pool
from ...db.logger import get_logger
from .api_client import FootyStatsClient
from ...normalizer.team_resolver import TeamResolver, MatchResolver

logger = get_logger(__name__)


class FixturesCollector:
    def __init__(self, api_client: FootyStatsClient):
        self.api_client = api_client
        self._pool = None

    async def _init_db(self):
        if self._pool is None:
            self._pool = await get_pool()

    async def collect_active_seasons(self):
        """
        Coleta fixtures para todas as seasons marcadas como ativas.
        """
        await self._init_db()
        
        async with self._pool.acquire() as conn:
            active_seasons = await conn.fetch(
                """
                SELECT season_id, league_id, footystats_season_id 
                FROM seasons 
                WHERE is_current = TRUE AND footystats_season_id IS NOT NULL
                """
            )
        
        logger.info("fixtures_collector_start", active_seasons=len(active_seasons))
        
        team_resolver = TeamResolver(self._pool)
        await team_resolver.load_cache()
        match_resolver = MatchResolver(self._pool, team_resolver)

        upserted_total = 0
        
        for sess in active_seasons:
            fs_season_id = sess['footystats_season_id']
            # Para FootyStats, buscar fixtures geralmente significa recarregar a season 
            # (pois a API devolve schedule também) ou usar a rota `league-matches`. 
            # Aproveitando que traz all, o matches-results traz todo mundo inclusive futuros se existirem.
            # Footystats `league-matches` documenta trazer fixtures pro futuro caso o season_id esteja ativo.
            
            matches = await self.api_client.fetch_season_matches(fs_season_id)
            if not matches:
                continue
                
            # Filtra so os scheduled / incomplete
            scheduled = [m for m in matches if m.get('status', '').lower() in ('incomplete', 'scheduled', 'suspended')]
            if not scheduled:
                continue

            async with self._pool.acquire() as conn:
                for m in scheduled:
                    home_name = str(m.get('home_name', ''))
                    away_name = str(m.get('away_name', ''))
                    unix_t = m.get('date_unix')
                    if not unix_t or not home_name or not away_name:
                        continue
                        
                    kickoff_dt = datetime.fromtimestamp(unix_t, tz=timezone.utc)
                    fs_id = m.get('id')
                    
                    home_id = await team_resolver.resolve("footystats", home_name)
                    away_id = await team_resolver.resolve("footystats", away_name)
                    
                    if not home_id or not away_id:
                        # Se não existe pra fixture, como é agendado, a gente loga e pula (ou insere em staging).
                        # O seed/backfill já vai ter criado os alias pra 99%.
                        logger.warning("fixture_unresolved_team", home=home_name, away=away_name)
                        continue

                    match_id = await match_resolver.resolve(
                        league_id=sess['league_id'],
                        home_name=home_name,
                        away_name=away_name,
                        kickoff_date=kickoff_dt.date(),
                        source="footystats"
                    )
                    
                    if match_id:
                        # Atualiza se baseou na football-data
                        await conn.execute(
                            """
                            UPDATE matches 
                            SET footystats_id = $1, kickoff = $2, status = 'scheduled', updated_at = NOW()
                            WHERE match_id = $3
                            """, 
                            fs_id, kickoff_dt, match_id
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO matches (
                                season_id, league_id, home_team_id, away_team_id, 
                                kickoff, status, footystats_id, updated_at
                            ) VALUES ($1, $2, $3, $4, $5, 'scheduled', $6, NOW())
                            ON CONFLICT DO NOTHING
                            """,
                            sess['season_id'], sess['league_id'], home_id, away_id, kickoff_dt, fs_id
                        )
                    upserted_total += 1
                    
        return upserted_total
