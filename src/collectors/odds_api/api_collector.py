import httpx
import asyncio
from datetime import datetime, timezone
import yaml
import os
from typing import List, Dict, Any, Optional
from uuid import UUID

from src.collectors.base import BaseCollector, CollectResult, CollectStatus
from src.scheduler.key_manager import KeyManager, NoKeysAvailableError
from src.normalizer.match_resolver import MatchResolver
from src.normalizer.team_resolver import TeamResolver
from src.normalizer.dedup import insert_odds_if_new
from src.db.pool import get_pool
from src.db.logger import get_logger

logger = get_logger(__name__)

# Mapeamento estático temporário para casas em Odds API -> Nossas configs
BOOKMAKER_ALIASES = {
    "pinnacle": "pinnacle",
    "betfair_exchange": "betfair_ex",
    "bet365": "bet365"
}

MARKET_MAPPINGS = {
    "h2h": "1x2",
    "spreads": "ah",
    "totals": "ou"
}

class OddsApiCollector(BaseCollector):
    def __init__(self):
        super().__init__("odds_api")
        self.base_url = "https://api.the-odds-api.com/v4"
        self._load_config()

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'leagues.yaml')
        bm_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'bookmakers.yaml')
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.leagues_config = yaml.safe_load(f).get('leagues', {})
            
        with open(bm_path, 'r', encoding='utf-8') as f:
            self.bm_config = yaml.safe_load(f).get('bookmakers', {})
            
        # Reverse map display names/aliases to IDs se BookmakerResolver não estiver definido globalmente
        # Considerando que ID da casa é um int gerado, usaremos o DB pra pegar IDs reais
        self.bm_ids = {}

    async def _init_bm_ids(self, conn):
        if not self.bm_ids:
            rows = await conn.fetch("SELECT bookmaker_id, name FROM bookmakers")
            for row in rows:
                self.bm_ids[row['name']] = row['bookmaker_id']

    async def _get_budget_tier(self) -> int:
        try:
            budget = await KeyManager.get_service_budget("odds_api")
            remaining = budget["total_limit_monthly"] - budget["total_usage_month"]
            
            if remaining < 200:
                logger.warning("odds_api_budget_critical", remaining=remaining)
                return 3  # Apenas fallback
            elif remaining < 500:
                return 2  # Snapshot + fallback
            else:
                return 1  # Validação completa
        except Exception as e:
            logger.error("odds_api_budget_error", error=str(e))
            return 1 # default
            
    def _get_target_leagues(self, tier: int, mode: str) -> List[tuple]:
        """ Retorna lista de (league_code, sport_key, tier_num) """
        targets = []
        for code, league in self.leagues_config.items():
            sport_key = league.get("odds_api_sport_key")
            if not sport_key:
                continue
                
            league_tier = league.get("tier", 3)
            
            # Filtro baseado na mode e budget_tier
            if mode == "validation" and tier == 1:
                if league_tier <= 2:
                    targets.append((code, sport_key, league_tier))
            elif mode == "prematch" and tier <= 2:
                targets.append((code, sport_key, league_tier))
            elif mode == "fallback":
                # Fallback atinge as ligas alvo necessárias sob demanda
                targets.append((code, sport_key, league_tier))
                
        return targets

    async def fetch_odds(self, sport_key: str, api_key: str) -> List[dict]:
        url = f"{self.base_url}/sports/{sport_key}/odds"
        
        bm_keys_list = [
            bm.get("odds_api_key") 
            for bm in self.bm_config.values() 
            if isinstance(bm, dict) and bm.get("odds_api_key")
        ]
        # Se bm_config for vazio, usamos o fallback nativo das 3 casas principais
        bm_str = ",".join(bm_keys_list) if bm_keys_list else "pinnacle,betfair_exchange,bet365"
        
        params = {
            "apiKey": api_key,
            "regions": "eu,uk",
            "markets": "h2h,spreads,totals",
            "bookmakers": bm_str,
            "oddsFormat": "decimal"
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=15.0)
            resp.raise_for_status()
            return resp.json()

    async def fetch_odds_single(self, sport_key: str, event_id: str, api_key: str) -> dict:
        url = f"{self.base_url}/sports/{sport_key}/events/{event_id}/odds"
        bm_keys_list = [
            bm.get("odds_api_key") for bm in self.bm_config.values() 
            if isinstance(bm, dict) and bm.get("odds_api_key")
        ]
        bm_str = ",".join(bm_keys_list) if bm_keys_list else "pinnacle,betfair_exchange,bet365"
        
        params = {
            "apiKey": api_key,
            "regions": "eu,uk",
            "markets": "h2h,spreads,totals",
            "bookmakers": bm_str,
            "oddsFormat": "decimal"
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=15.0)
            resp.raise_for_status()
            return resp.json()

    async def parse_and_insert(self, conn, events: List[dict], league_code: str, job_id: str) -> tuple[int, int]:
        records_collected = 0
        records_new = 0
        now = datetime.now(timezone.utc)
        
        await self._init_bm_ids(conn)
        
        for event in events:
            home_team = event['home_team']
            away_team = event['away_team']
            kickoff_str = event['commence_time']
            # Odds API ID extra para gravar se necessário
            # odds_api_id = event['id']
            
            # Match params pass date as date object (asyncpg requer date, não str)
            kickoff_date = datetime.fromisoformat(kickoff_str.replace('Z', '+00:00')).date()
            
            league_id = await conn.fetchval("SELECT league_id FROM leagues WHERE code = $1", league_code)
            if not league_id: continue
            
            match_id = await MatchResolver.resolve(league_id, home_team, away_team, kickoff_date, "odds_api")
            if not match_id:
                logger.info("match_not_resolved", source="odds_api", home=home_team, away=away_team, date=kickoff_date)
                continue
            
            # Grava api id no match
            await conn.execute("UPDATE matches SET odds_api_id = $1 WHERE match_id = $2", event['id'], match_id)
                
            for bm in event.get('bookmakers', []):
                bm_key = bm['key']
                our_bm_key = BOOKMAKER_ALIASES.get(bm_key)
                if not our_bm_key or our_bm_key not in self.bm_ids: continue
                bm_id = self.bm_ids[our_bm_key]
                
                for market in bm.get('markets', []):
                    market_key = market['key']
                    our_market = MARKET_MAPPINGS.get(market_key)
                    if not our_market: continue
                    
                    records_collected += 1
                    outcomes = market.get('outcomes', [])
                    
                    if our_market == "1x2":
                        odds_1 = next((o['price'] for o in outcomes if o['name'] == home_team), None)
                        odds_2 = next((o['price'] for o in outcomes if o['name'] == away_team), None)
                        odds_x = next((o['price'] for o in outcomes if o['name'] == 'Draw'), None)
                        line = None
                        
                        # Verifica se é a primeira vez que coletamos odds para este match/market/bookie
                        has_previous = await conn.fetchval(
                            "SELECT 1 FROM odds_history WHERE match_id = $1 AND bookmaker_id = $2 AND market_type = $3 LIMIT 1",
                            match_id, bm_id, our_market
                        )
                        _is_opening = not bool(has_previous)
                        
                        is_new = await insert_odds_if_new(
                            conn=conn, match_id=match_id, bookmaker_id=bm_id, market_type=our_market,
                            line=line, period="ft", odds_1=odds_1, odds_x=odds_x, odds_2=odds_2,
                            source="odds_api", collect_job_id=job_id, is_opening=_is_opening, time=now
                        )
                        if is_new: records_new += 1
                        
                    elif our_market in ("ah", "ou"):
                        # agrupar outcomes by point para AH e OU
                        grouped = {}
                        for o in outcomes:
                            pt = o.get('point')
                            if pt is None: continue
                            if pt not in grouped: grouped[pt] = {}
                            grouped[pt][o['name']] = o['price']
                            
                        for pt, points_dict in grouped.items():
                            odds_1, odds_x, odds_2 = None, None, None
                            
                            if our_market == "ou":
                                odds_1 = points_dict.get('Over')
                                odds_2 = points_dict.get('Under')
                            elif our_market == "ah":
                                odds_1 = points_dict.get(home_team)
                                odds_2 = points_dict.get(away_team)
                                
                            line_f = float(pt)
                            has_previous = await conn.fetchval(
                                "SELECT 1 FROM odds_history WHERE match_id = $1 AND bookmaker_id = $2 AND market_type = $3 AND line IS NOT DISTINCT FROM $4 LIMIT 1",
                                match_id, bm_id, our_market, line_f
                            )
                            _is_opening = not bool(has_previous)
                            
                            is_new = await insert_odds_if_new(
                                conn=conn, match_id=match_id, bookmaker_id=bm_id, market_type=our_market,
                                line=line_f, period="ft", odds_1=odds_1, odds_x=odds_x, odds_2=odds_2,
                                source="odds_api", collect_job_id=job_id, is_opening=_is_opening, time=now
                            )
                            if is_new: records_new += 1

        return records_collected, records_new

    async def collect_single(self, match_id_uuid: str) -> CollectResult:
        job_id = self.generate_job_id("odds_api_single_match")
        started_at = datetime.now(timezone.utc)
        
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Pega o league_id e odds_api_id
            try:
                parsed_uuid = UUID(str(match_id_uuid))
            except Exception:
                parsed_uuid = match_id_uuid # fallback just in case it's somehow valid or not parseable
                
            row = await conn.fetchrow("""
                SELECT m.odds_api_id, l.code
                FROM matches m
                JOIN leagues l ON m.league_id = l.league_id
                WHERE m.match_id = $1
            """, parsed_uuid)
            
            if not row or not row['odds_api_id']:
                logger.info("single_match_skipped_no_id", match_id=match_id_uuid)
                return CollectResult(
                    source=self.source_name, job_type="single_match", job_id=job_id,
                    status=CollectStatus.SUCCESS, started_at=started_at, finished_at=datetime.now(timezone.utc),
                    records=[], metadata={"reason": "No odds_api_id linked to this match yet"}
                )
                
            odds_api_id = row['odds_api_id']
            league_code = row['code']
            sport_key = self.leagues_config.get(league_code, {}).get("odds_api_sport_key")
            
            if not sport_key:
                return CollectResult(
                    source=self.source_name, job_type="single_match", job_id=job_id,
                    status=CollectStatus.FAILED, started_at=started_at, finished_at=datetime.now(timezone.utc),
                    records=[], errors=["No odds_api_sport_key configured for league"]
                )
                
            try:
                api_key = await KeyManager.get_key("odds_api")
                event_data = await self.fetch_odds_single(sport_key, odds_api_id, api_key)
                
                # event_data format for single event is exactly a single dict matching what is returned inside the list for /odds!
                c, n = await self.parse_and_insert(conn, [event_data], league_code, job_id)
                
                return CollectResult(
                    source=self.source_name, job_type="single_match", job_id=job_id, status=CollectStatus.SUCCESS,
                    started_at=started_at, finished_at=datetime.now(timezone.utc),
                    records=[], records_collected=c, records_new=n, errors=[]
                )
            except NoKeysAvailableError as e:
                logger.error("odds_api_keys_depleted")
                return CollectResult(
                    source=self.source_name, job_type="single_match", job_id=job_id, status=CollectStatus.FAILED,
                    started_at=started_at, finished_at=datetime.now(timezone.utc),
                    records=[], records_collected=0, records_new=0, errors=[str(e)]
                )
            except Exception as e:
                logger.error("odds_api_fetch_error", match_id=match_id_uuid, error=str(e))
                return CollectResult(
                    source=self.source_name, job_type="single_match", job_id=job_id, status=CollectStatus.FAILED,
                    started_at=started_at, finished_at=datetime.now(timezone.utc),
                    records=[], records_collected=0, records_new=0, errors=[str(e)]
                )

    async def collect(self, mode: str = "validation", **kwargs) -> CollectResult:
        if mode == "single_match":
            return await self.collect_single(kwargs.get("match_id"))
            
        valid_modes = {"validation", "prematch", "fallback"}
        if mode not in valid_modes:
            raise ValueError(f"Mode inválido para OddsApiCollector: {mode}. Use: {valid_modes}")
            
        job_id = self.generate_job_id(f"odds_api_{mode}")
        started_at = datetime.now(timezone.utc)
        
        # Garante que o cache de aliases está carregado (inclusive novos aliases recém-inseridos)
        await TeamResolver.load_cache()
        
        pool = await get_pool()
        async with pool.acquire() as conn:
            tier = await self._get_budget_tier()
            targets = self._get_target_leagues(tier, mode)
            
            if not targets:
                return CollectResult(
                    source=self.source_name, job_type=mode, job_id=job_id,
                    status=CollectStatus.SUCCESS, started_at=started_at,
                    finished_at=datetime.now(timezone.utc), records=[],
                    metadata={"reason": "No target leagues for current tier"}
                )

            total_collected, total_new, total_skipped = 0, 0, 0
            errors = []
            
            for code, sport_key, league_tier in targets:
                try:
                    # Request needs 1 request per league
                    api_key = await KeyManager.get_key("odds_api")
                    events = await self.fetch_odds(sport_key, api_key)
                    
                    c, n = await self.parse_and_insert(conn, events, code, job_id)
                    total_collected += c
                    total_new += n
                    total_skipped += (c - n)
                    
                    await asyncio.sleep(2) # Rate limiting the Odds API Requests properly
                except NoKeysAvailableError as e:
                    logger.error("odds_api_keys_depleted")
                    errors.append(str(e))
                    break # Stop looping leagues if keys depleted
                except Exception as e:
                    logger.error("odds_api_fetch_error", league=code, error=str(e))
                    errors.append(str(e))

            status = CollectStatus.FAILED if len(errors) == len(targets) and targets else \
                     CollectStatus.PARTIAL if errors else CollectStatus.SUCCESS

            return CollectResult(
                source=self.source_name, job_type=mode, job_id=job_id, status=status,
                started_at=started_at, finished_at=datetime.now(timezone.utc),
                records=[], records_collected=total_collected,
                records_new=total_new, records_skipped=total_skipped, errors=errors
            )

    async def health_check(self) -> bool:
        try:
            # Endpoint /sports é free da Odds API, portanto não incide quota (requests_needed=0 está ok)
            api_key = await KeyManager.get_key("odds_api", requests_needed=0)
            url = f"{self.base_url}/sports?apiKey={api_key}"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10.0)
                return resp.status_code == 200
        except Exception:
            return False
