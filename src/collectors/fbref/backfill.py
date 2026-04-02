"""
T08 — FBRef Backfill Orchestrator
Estratégia: Indexa a schedule global primeiro gravando IDs, depois faz o Backfill assíncrono blindado no match level.
"""
import sys
import asyncio
import argparse
import json
import yaml
from pathlib import Path

import unicodedata
from datetime import datetime

from bs4 import BeautifulSoup
from ...db.pool import get_pool
from ...db.logger import get_logger
from ...normalizer.team_resolver import TeamResolver
from ...normalizer.match_resolver import MatchResolver
from .api_client import FBRefClient, RateLimitedException
from .parser import FBRefParser

logger = get_logger(__name__)

class FBRefBackfill:
    def __init__(self, db_pool, client: FBRefClient):
        self._pool = db_pool
        self.client = client
        self.base_url = "https://fbref.com"

        # Lembre-se: FBRef usa "ENG-Premier-League" como identifier nas views, precisaremos dele + comp_id.
        
    async def init_caches(self):
        await TeamResolver.load_cache()

    async def index_season(self, league_id: int, fbref_comp_id: str, season_label: str, comp_name_slug: str):
        """
        Passo 1: Varre o Match Schedule (1 Req / temporada / liga) e aloca o fbref_id bruto.
        Ex: /en/comps/9/2023-2024/schedule/2023-2024-Premier-League-Scores-and-Fixtures
        """
        url = f"{self.base_url}/en/comps/{fbref_comp_id}/{season_label}/schedule/{season_label}-{comp_name_slug}-Scores-and-Fixtures"
        logger.info("fbref_indexing_season", url=url, league_id=league_id)

        try:
            html = await self.client.fetch_html(url)
        except Exception as e:
            logger.error("fbref_index_failed", url=url, error=str(e))
            return

        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", {"id": lambda L: L and L.startswith("sched")})
        
        if not table:
            logger.warning("fbref_schedule_not_found", url=url)
            return

        rows = table.find("tbody").find_all("tr")
        matched_count = 0

        async with self._pool.acquire() as conn:
            already_indexed = set(
                r['fbref_id'] for r in await conn.fetch(
                    "SELECT fbref_id FROM matches WHERE league_id = $1 AND fbref_id IS NOT NULL",
                    league_id
                )
            )

            for row in rows:
                if "spacer" in row.get("class", []):
                    continue
                
                date_td = row.find("td", {"data-stat": "date"})
                match_report_td = row.find("td", {"data-stat": "match_report"})
                home_td = row.find("td", {"data-stat": "home_team"})
                away_td = row.find("td", {"data-stat": "away_team"})

                if not date_td or not match_report_td or not home_td or not away_td:
                    continue

                a_tag = match_report_td.find("a")
                if not a_tag or "matches" not in a_tag.get("href", ""):
                    # O Jogo ainda não aconteceu ou não tem estatísticas publicadas.
                    continue
                
                # Extraindo o Hash. Href clássico: /en/matches/18bb7c10/Arsenal-Liverpool-Premier-League
                fbref_id = a_tag["href"].split("/")[3]
                
                if fbref_id in already_indexed:
                    continue

                date_str = date_td.text.strip()
                
                def _clean_slug(raw: str) -> str:
                    normalized = unicodedata.normalize("NFKC", raw.strip())
                    return normalized.replace(" ", "-")

                home_slug = _clean_slug(home_td.text)
                away_slug = _clean_slug(away_td.text)

                match_id = await MatchResolver.resolve(
                    league_id=league_id,
                    home_name=home_slug,
                    away_name=away_slug,
                    kickoff_date=datetime.strptime(date_str, "%Y-%m-%d").date(),
                    source="fbref"
                )

                if match_id:
                    await conn.execute(
                        "UPDATE matches SET fbref_id = $1, updated_at = NOW() WHERE match_id = $2 AND fbref_id IS NULL",
                        fbref_id, match_id
                    )
                    matched_count += 1

        logger.info("fbref_season_indexed", matched=matched_count, season=season_label)

    async def process_pending_matches(self):
        """Passo 2: Varre ligas FBRef no DB buscando jogos terminados que não receberam a carga do source=fbref em match_stats"""
        
        query = """
            SELECT m.match_id, m.fbref_id 
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.fbref_id IS NOT NULL 
              AND l.xg_source = 'fbref'
              AND NOT EXISTS (
                  SELECT 1 FROM match_stats ms 
                  WHERE ms.match_id = m.match_id AND ms.source = 'fbref'
              )
            ORDER BY m.kickoff DESC
        """
        async with self._pool.acquire() as conn:
            missing_matches = await conn.fetch(query)

        logger.info("fbref_pending_matches", count=len(missing_matches))
        if not missing_matches:
            return

        for row in missing_matches:
            match_id = row['match_id']
            fbref_id = row['fbref_id']
            # O sistema de rotas da FBRef consegue localizar o jogo somente com o Hash, ignorando o match-name real.
            # /en/matches/18bb7c10/ -> Redireciona 301 para a página final ou já processa o HTML nativo
            url = f"{self.base_url}/en/matches/{fbref_id}/"
            
            try:
                html = await self.client.fetch_html(url)
                match_data = FBRefParser.parse_match(html)
                
                aggregated = match_data.get("aggregated", {})
                
                # Caso a url tenha dado 200 mas a FBRef realmente esvaziou a página por ser antiguidade extrema
                if not aggregated:
                    logger.warning("fbref_stats_unavailable", fbref_id=fbref_id, match_id=match_id)
                    # Insert NULL para selar o status de 'Visto sem sucesso'
                    await self._upsert_match_stats(match_id, None, None, {"_no_data": True})
                    continue

                raw_json = {
                    "home_players": match_data["home_players"],
                    "away_players": match_data["away_players"],
                    "aggregated": aggregated
                }
                
                await self._upsert_match_stats(match_id, aggregated.get("xg_home"), aggregated.get("xg_away"), raw_json)
                logger.info("fbref_stats_upserted", match_id=match_id, fbref_id=fbref_id)
            
            except RateLimitedException:
                logger.error("fbref_banned_stopping", fbref_id=fbref_id)
                break  # Ban real duradouro -> mata loop de backfill inteiro pra não spammar.
                
            except Exception as e:
                logger.error("fbref_stats_failed", fbref_id=fbref_id, error=str(e))
                # Erro orgânico (HTML quebrado, parse vazio). Segue baile.
                continue

    async def _upsert_match_stats(self, match_id: str, xg_home, xg_away, raw_json: dict):
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO match_stats (match_id, source, xg_home, xg_away, raw_json)
                VALUES ($1, 'fbref', $2, $3, $4::jsonb)
                ON CONFLICT (match_id, source) DO UPDATE 
                SET xg_home = EXCLUDED.xg_home,
                    xg_away = EXCLUDED.xg_away,
                    raw_json = EXCLUDED.raw_json,
                    updated_at = NOW()
            """, match_id, xg_home, xg_away, json.dumps(raw_json))


async def main_backfill():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-only", action="store_true", help="Baixa apenas O HTML do calendário")
    parser.add_argument("--process-only", action="store_true", help="Roda o loop dos jogos sem indexar antes")
    args = parser.parse_args()

    db_pool = await get_pool()
    client = FBRefClient(cooldown=3.5)
    orchestrator = FBRefBackfill(db_pool, client)
    
    await orchestrator.init_caches()

    # Leitura das configurações
    config_path = Path("src/config/leagues.yaml")
    if not config_path.exists():
        logger.error("config_not_found", path=str(config_path))
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        leagues_config = yaml.safe_load(f).get("leagues", {})

    try:
        # STEP 1: INDEX
        if not args.process_only:
            async with db_pool.acquire() as conn:
               # Busca da tabela original os IDs reais gerados para linkarmos com o name key do yaml.
               league_db_mapping = {r['code']: r['league_id'] for r in await conn.fetch("SELECT code, league_id FROM leagues")}

            for code, data in leagues_config.items():
                if data.get("xg_source") == "fbref":
                    league_id = league_db_mapping.get(code)
                    if not league_id:
                         continue
                         
                    fbref_id_comp = data.get("fbref_id")
                    
                    # Nome amigavel usado na URL da season
                    # Ex: 'Premier League' vira 'Premier-League'
                    comp_name_slug = data.get("name").replace(" ", "-")

                    for season_key in data.get("seasons", {}):
                        # season_key = "2023/2024"
                        season_label = season_key.replace("/", "-")
                        await orchestrator.index_season(league_id, fbref_id_comp, season_label, comp_name_slug)

        # STEP 2: BACKFILL MATCH STATS (Upsert pesado)
        if not args.index_only:
            await orchestrator.process_pending_matches()
            
    finally:
        await client.close()
        await db_pool.close()

if __name__ == "__main__":
    asyncio.run(main_backfill())
