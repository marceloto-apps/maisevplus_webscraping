"""
T07 — Understat Backfill Script
Realiza dump histórico completo da Understat (shot data),
com checkpoint persistente para sobreviver a bans.
"""
import os
import json
import asyncio
from typing import List, Dict
from datetime import datetime
from pathlib import Path

from ...db import get_pool
from ...db.logger import get_logger
from .scraper import UnderstatScraper
from .shot_collector import ShotCollector
from ...normalizer.team_resolver import TeamResolver, MatchResolver
import yaml

logger = get_logger(__name__)

CONCURRENCY = 3
DELAY_BETWEEN = 1.0
CHECKPOINT_FILE = Path("output/.understat_checkpoint")

class UnderstatBackfill:
    def __init__(self, scraper: UnderstatScraper):
        self.scraper = scraper
        self._pool = None

    async def _init_db(self):
        if self._pool is None:
            self._pool = await get_pool()

    async def run(self):
        await self._init_db()
        yaml_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "leagues.yaml")
        with open(yaml_path, "r", encoding="utf-8") as f:
            leagues_cfg = yaml.safe_load(f).get("leagues", {})
        
        # Filtrar as ligas suportadas (tem understat_name != null)
        target_seasons = []
        for l_key, conf in leagues_cfg.items():
            u_name = conf.get("understat_name")
            if not u_name:
                continue
            for s_key, s_data in conf.get("seasons", {}).items():
                target_seasons.append({
                    "understat_name": u_name,
                    "understat_season": s_key.split("/")[0] # formato 2021/2022 -> 2021
                })
        
        logger.info("understat_backfill_leagues", count=len(target_seasons))

        all_matches_to_fetch = []
        for sess in target_seasons:
            matches_meta = await self.scraper.fetch_league_matches(sess['understat_name'], sess['understat_season'])
            if matches_meta:
                all_matches_to_fetch.extend(matches_meta)
            await asyncio.sleep(DELAY_BETWEEN)
            
        total_matches = len(all_matches_to_fetch)
        logger.info("understat_matches_meta_fetched", total=total_matches)

        last_checkpoint = 0
        if CHECKPOINT_FILE.exists():
            try:
                last_checkpoint = int(CHECKPOINT_FILE.read_text().strip())
                logger.info("understat_checkpoint_loaded", index=last_checkpoint)
            except ValueError:
                pass

        if last_checkpoint >= total_matches:
            logger.info("understat_backfill_already_done")
            return

        team_resolver = TeamResolver(self._pool)
        await team_resolver.load_cache()
        match_resolver = MatchResolver(self._pool, team_resolver)

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def process_match(index: int, m_meta: dict):
            async with semaphore:
                try:
                    await self._process_single_match(index, m_meta, match_resolver, total_matches)
                except Exception as e:
                    logger.error("understat_match_error", match_id=m_meta.get('id'), error=str(e))
                finally:
                    await asyncio.sleep(DELAY_BETWEEN)
        
        # Slice the remaining jobs
        pending = list(enumerate(all_matches_to_fetch))[last_checkpoint:]
        
        # Roda em blocos de batch para não explodir memoria do asyncio
        chunk_size = 50
        for i in range(0, len(pending), chunk_size):
            chunk = pending[i:i+chunk_size]
            await asyncio.gather(*[process_match(idx, meta) for idx, meta in chunk])
            
            # Safe checkpoint per tiny batch
            last_idx = chunk[-1][0]
            CHECKPOINT_FILE.write_text(str(last_idx + 1))

        logger.info("understat_backfill_done")

    async def _process_single_match(self, idx: int, m_meta: dict, match_resolver: MatchResolver, total: int):
        u_match_id = m_meta.get('id')
        parsed_dt = datetime.strptime(m_meta['datetime'], "%Y-%m-%d %H:%M:%S")
        h_name = m_meta['h']['title']
        a_name = m_meta['a']['title']

        if (idx + 1) % 10 == 0:
            logger.info("backfill_progress", current=idx+1, total=total, pct=f"{(idx+1)/total*100:.1f}%")

        # Prioridade 2 e 3
        # No understat a liga esta implicita pela meta data, mas precisamos achar pra nossa BD
        async with self._pool.acquire() as conn:
            # Pega o league_id via db pelo understat_name (a gente parseou home/away cruzando)
            # ou cruza direito nomes
            pass

        # Para facilitar a resoluçao, iteramos as prioridades sem estarmos agarrados à um League ID, 
        # ja que as strings dos matches na DB já tem times unicos no mundo:
        # Porem o match_resolver atual requer league_id.
        async with self._pool.acquire() as conn:
            home_id = await match_resolver._team_resolver.resolve("understat", h_name)
            away_id = await match_resolver._team_resolver.resolve("understat", a_name)

            if not home_id or not away_id:
                return # Time nao resolvido

            # Acha o match
            rows = await conn.fetch(
                """
                SELECT match_id FROM matches
                WHERE home_team_id = $1 AND away_team_id = $2
                  AND ABS(kickoff::date - $3::date) <= 1
                """, home_id, away_id, parsed_dt.date()
            )
            
            if len(rows) != 1:
                if len(rows) > 1:
                    logger.warning("fuzzy_match_ambiguous", count=len(rows), home=home_name, away=away_name)
                return

            match_id = rows[0]['match_id']

            # Extração
            shots_data = await self.scraper.fetch_match_shots(u_match_id)
            if not shots_data:
                return
            
            metrics = ShotCollector.extract_metrics(shots_data)
            
            # Upsert
            await conn.execute(
                """
                INSERT INTO match_stats (
                    match_id, source, xg_home, xg_away, raw_json, collected_at
                ) VALUES (
                    $1, 'understat', $2, $3, $4, NOW()
                )
                ON CONFLICT (match_id, source) DO UPDATE SET
                    xg_home = EXCLUDED.xg_home,
                    xg_away = EXCLUDED.xg_away,
                    raw_json = EXCLUDED.raw_json,
                    collected_at = EXCLUDED.collected_at
                """,
                match_id, metrics.get('xg_home'), metrics.get('xg_away'), json.dumps(metrics.get('raw_json'))
            )
