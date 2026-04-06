import httpx
import asyncio
import json
from datetime import datetime, timezone
import yaml
import os
from typing import List, Dict, Any, Optional
from uuid import UUID

from src.collectors.base import BaseCollector, CollectResult, CollectStatus
from src.scheduler.key_manager import KeyManager, NoKeysAvailableError
from src.normalizer.match_resolver import MatchResolver
from src.normalizer.team_resolver import TeamResolver
from src.db.pool import get_pool
from src.db.logger import get_logger
from src.db import helpers

logger = get_logger(__name__)

class ApiFootballCollector(BaseCollector):
    def __init__(self):
        super().__init__("api_football")
        self.base_url = "https://v3.football.api-sports.io"
        self._load_config()

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'leagues.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            self.leagues_config = yaml.safe_load(f).get('leagues', {})

    async def _fetch(self, endpoint: str, api_key: str, params: dict = None) -> dict:
        url = f"{self.base_url}{endpoint}"
        headers = {"x-apisports-key": api_key}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, params=params, timeout=15.0)
            resp.raise_for_status()
            return resp.json()

    async def discover_fixture_ids(self, date_from: str, date_to: str) -> CollectResult:
        """
        Executado semanalmente para parear IDs externos da api_football às nossas fixtures no DB.
        """
        job_id = self.generate_job_id("api_football_discovery")
        started_at = datetime.now(timezone.utc)
        
        total_discovered = 0
        errors = []
        
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                for code, league in self.leagues_config.items():
                    af_id = league.get("api_football_league_id")
                    if not af_id: continue
                    
                    try:
                        records = await self._sync_fixtures_for_league(conn, code, af_id, date_from, date_to)
                        total_discovered += records
                        await asyncio.sleep(7) # Rate limiting de 10 req/min
                    except NoKeysAvailableError as e:
                        errors.append(str(e))
                        break
                    except Exception as e:
                        logger.error("api_football_discovery_error", error=str(e), league=code)
                        errors.append(str(e))
        except Exception as e:
            errors.append(str(e))
            
        status = CollectStatus.FAILED if errors and total_discovered == 0 else \
                 CollectStatus.PARTIAL if errors else CollectStatus.SUCCESS
                 
        return CollectResult(
            source=self.source_name, job_type="discovery", job_id=job_id,
            status=status, started_at=started_at, finished_at=datetime.now(timezone.utc),
            records=[], records_collected=total_discovered, records_new=total_discovered
        )

    async def _sync_fixtures_for_league(self, conn, league_code: str, af_league_id: int, date_from: str, date_to: str) -> int:
        now = datetime.now(timezone.utc)
        season = now.year
        if now.month < 7 and self.leagues_config.get(league_code, {}).get("season_format") == "aug_may":
            season -= 1
            
        api_key = await KeyManager.get_key("api_football")
        data = await self._fetch("/fixtures", api_key, {
            "league": af_league_id,
            "season": season,
            "from": date_from,
            "to": date_to
        })
        
        records = 0
        fixtures = data.get("response", [])
        league_id_db = await conn.fetchval("SELECT league_id FROM leagues WHERE code = $1", league_code)
        if not league_id_db: return 0
        
        for f in fixtures:
            fixture_id = f["fixture"]["id"]
            kickoff_date = datetime.fromisoformat(f["fixture"]["date"].split('T')[0]).date()
            home_str = f["teams"]["home"]["name"]
            away_str = f["teams"]["away"]["name"]
            
            match_id = await MatchResolver.resolve(league_id_db, home_str, away_str, kickoff_date, "api_football")
            if match_id:
                await conn.execute("UPDATE matches SET api_football_id = $1 WHERE match_id = $2", str(fixture_id), match_id)
                records += 1
                
        return records

    async def collect_lineups(self, match_id_uuid_str: str) -> CollectResult:
        job_id = self.generate_job_id("api_football_lineups")
        started_at = datetime.now(timezone.utc)
        
        errors = []
        status = CollectStatus.FAILED
        records_collected = 0
        records_new = 0
        
        try:
            match_id_uuid = UUID(str(match_id_uuid_str))
            pool = await get_pool()
            async with pool.acquire() as conn:
                # Obter api_football_id do DB
                row = await conn.fetchrow("SELECT api_football_id, league_id, home_team_id, away_team_id, kickoff FROM matches WHERE match_id = $1", match_id_uuid)
                if not row:
                    raise Exception("Match not found")
                    
                af_id = row['api_football_id']
                if not af_id:
                    # Tentar fazer lookup on-demand se não temos o af_id
                    league_code = await conn.fetchval("SELECT code FROM leagues WHERE league_id = $1", row['league_id'])
                    af_league_id = self.leagues_config.get(league_code, {}).get('api_football_league_id')
                    
                    if af_league_id:
                        api_key = await KeyManager.get_key("api_football")
                        data = await self._fetch("/fixtures", api_key, {
                            "league": af_league_id,
                            "date": str(row['kickoff'].date())
                        })
                        
                        for f in data.get('response', []):
                            t_name = f["teams"]["home"]["name"]
                            resolved_id = await TeamResolver.resolve(t_name, "api_football")
                            if resolved_id == row['home_team_id']:
                                af_id = str(f["fixture"]["id"])
                                await conn.execute("UPDATE matches SET api_football_id = $1 WHERE match_id = $2", af_id, match_id_uuid)
                                break
                    
                if not af_id:
                    raise Exception("Could not resolve api_football_id for match")
                
                # Buscar escalacoes reais
                api_key = await KeyManager.get_key("api_football")
                lineup_data = await self._fetch("/fixtures/lineups", api_key, {"fixture": af_id})
                
                lineups = lineup_data.get('response', [])
                if not lineups:
                    # Empty lineups (Not confirmed yet)
                    logger.warning("api_football_lineups_empty", match_id=str(match_id_uuid))
                    status = CollectStatus.PARTIAL
                    return CollectResult(
                        source=self.source_name, job_type="lineups", job_id=job_id,
                        status=status, started_at=started_at, finished_at=datetime.now(timezone.utc),
                        records=[], records_collected=0, records_new=0, errors=["Empty lineups"],
                        metadata={"retry_requested": True}
                    )
                else:
                    status = CollectStatus.SUCCESS
                    for team_lineup in lineups:
                        # Extract players
                        startXI = []
                        for p in team_lineup.get('startXI', []):
                            player = p['player']
                            startXI.append({
                                "name": player['name'],
                                "number": player['number'],
                                "pos": player['pos'],
                                "grid": player['grid']
                            })
                            
                        substitutes = []
                        for p in team_lineup.get('substitutes', []):
                            player = p['player']
                            substitutes.append({
                                "name": player['name'],
                                "number": player['number'],
                                "pos": player['pos'],
                                "grid": player['grid']
                            })
                            
                        formation = team_lineup.get('formation', 'Unknown')
                        coach = team_lineup.get('coach', {}).get('name')
                        
                        players_json = {
                            "formation": formation,
                            "coach": coach,
                            "startXI": startXI,
                            "substitutes": substitutes
                        }
                        
                        # Definir is_home usando TeamResolver para evitar falsos positivos
                        team_id = None
                        t_name = team_lineup["team"]["name"]
                        resolved_id = await TeamResolver.resolve(t_name, "api_football")
                        
                        is_home = False
                        if resolved_id == row['home_team_id']:
                            is_home = True
                            team_id = row['home_team_id']
                        elif resolved_id == row['away_team_id']:
                            is_home = False
                            team_id = row['away_team_id']
                        
                        if team_id:
                            # Upsert in lineups
                            upsert_query = """
                                INSERT INTO lineups (match_id, team_id, is_home, formation, players_json, source)
                                VALUES ($1, $2, $3, $4, $5::jsonb, 'api_football')
                                ON CONFLICT (match_id, team_id) DO UPDATE SET
                                    formation = EXCLUDED.formation,
                                    players_json = EXCLUDED.players_json,
                                    updated_at = NOW()
                            """
                            await conn.execute(upsert_query, match_id_uuid, team_id, is_home, formation, json.dumps(players_json))
                            records_collected += 1
                            records_new += 1
                            
        except Exception as e:
            logger.error("api_football_collect_error", match_id=str(match_id_uuid), error=str(e))
            errors.append(str(e))
            status = CollectStatus.FAILED
            
        return CollectResult(
            source=self.source_name, job_type="lineups", job_id=job_id,
            status=status, started_at=started_at, finished_at=datetime.now(timezone.utc),
            records=[], records_collected=records_collected, records_new=records_new, errors=errors
        )

    async def collect_fixtures(self, league_id_db: int, date_from: str, date_to: str) -> CollectResult:
        """Fallback method to grab fixtures when Footystats is down"""
        job_id = self.generate_job_id("api_football_fixtures_fallback")
        started_at = datetime.now(timezone.utc)
        errors = []
        records = 0
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                league_code = await conn.fetchval("SELECT code FROM leagues WHERE id = $1", league_id_db)
                af_league_id = self.leagues_config.get(league_code, {}).get('api_football_league_id')
                if not af_league_id:
                    raise Exception("No api_football_league_id mapping for league")
                    
                records = await self._sync_fixtures_for_league(conn, league_code, af_league_id, date_from, date_to)
                        
        except Exception as e:
            logger.error("api_football_fixtures_fallback_error", error=str(e))
            errors.append(str(e))
            
        return CollectResult(
            source=self.source_name, job_type="fixtures_fallback", job_id=job_id,
            status=CollectStatus.FAILED if errors else CollectStatus.SUCCESS,
            started_at=started_at, finished_at=datetime.now(timezone.utc),
            records=[], records_collected=records, records_new=records, errors=errors
        )

    async def collect(self, **kwargs) -> CollectResult:
        # Padrão: esse coletor deve ser chamado com um match_id ou com range para discovery
        mode = kwargs.get('mode')
        if mode == 'discovery':
            return await self.discover_fixture_ids(kwargs.get('date_from'), kwargs.get('date_to'))
        elif mode == 'lineup':
            return await self.collect_lineups(kwargs.get('match_id'))
        elif mode == 'fallback_fixtures':
            return await self.collect_fixtures(kwargs.get('league_id'), kwargs.get('date_from'), kwargs.get('date_to'))
        
        raise NotImplementedError("ApiFootballCollector exige mode='discovery', 'lineup' ou 'fallback_fixtures'")

    async def health_check(self) -> bool:
        try:
            api_key = await KeyManager.get_key("api_football", requests_needed=0)
            url = f"{self.base_url}/timezone"
            headers = {"x-apisports-key": api_key}
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=10.0)
                return resp.status_code == 200
        except Exception:
            return False
