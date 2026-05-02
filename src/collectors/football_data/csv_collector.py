"""
T05 — src/collectors/football_data/csv_collector.py
Coletor de dados históricos via CSV da football-data.co.uk.
Otimizado com pandas e httpx assíncrono.
"""

import argparse
import asyncio
import io
import os
import yaml
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
import pandas as pd

from ..base import BaseCollector, CollectResult, CollectStatus
from ...db import get_pool, fetch_val
from ...db.logger import get_logger
from ...normalizer.team_resolver import TeamResolver, MatchResolver
from ...normalizer.dedup import insert_odds_if_new

logger = get_logger(__name__)

MAIN_URL_TEMPLATE = "https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
EXTRA_URL_TEMPLATE = "https://www.football-data.co.uk/new/{code}.csv"


class FootballDataCollector(BaseCollector):
    def __init__(self):
        super().__init__("football_data")
        self._pool = None
        self._bookmaker_ids: Dict[str, int] = {}
        self._leagues_config: Dict[str, dict] = {}
        # Caches
        self._league_map: Dict[str, int] = {}  # football_data_code -> league_id
        self._season_map: Dict[tuple[int, str], int] = {}  # (league_id, fd_season) -> season_id
        self._extra_seasons: List[dict] = []   # [{season_id, league_id, start, end}, ...]

    async def _init_db_and_caches(self):
        """Inicializa conexões e caches dinâmicos do DB."""
        if self._pool is not None:
            return
        self._pool = await get_pool()
        
        # Load bookmakers
        self._bookmaker_ids['pinnacle'] = await fetch_val(
            "SELECT bookmaker_id FROM bookmakers WHERE name='pinnacle'"
        )
        self._bookmaker_ids['bet365'] = await fetch_val(
            "SELECT bookmaker_id FROM bookmakers WHERE name='bet365'"
        )
        self._bookmaker_ids['betfair_ex'] = await fetch_val(
            "SELECT bookmaker_id FROM bookmakers WHERE name='betfair_ex'"
        )

        # Load yaml config
        yaml_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "leagues.yaml")
        with open(yaml_path, "r", encoding="utf-8") as f:
            self._leagues_config = yaml.safe_load(f).get("leagues", {})

        # Load League IDs (matching by country & tier or understat_name)
        # Note: In a real scenario, we might want a direct mapping or DB query by name.
        # But since the config and DB are synchronized from T01, we fetch all leagues.
        async with self._pool.acquire() as conn:
            db_leagues = await conn.fetch("SELECT league_id, name, country FROM leagues")
            # Map by Name + Country robustly
            db_league_dict = {(r['name'], r['country']): r['league_id'] for r in db_leagues}

            for key, conf in self._leagues_config.items():
                l_id = db_league_dict.get((conf['name'], conf['country']))
                if l_id and conf.get("football_data_code"):
                    self._league_map[conf["football_data_code"]] = l_id

            # Load Seasons
            db_seasons = await conn.fetch(
                "SELECT season_id, league_id, football_data_season, start_date, end_date FROM seasons"
            )
            for s in db_seasons:
                if s["football_data_season"]:
                    self._season_map[(s["league_id"], s["football_data_season"])] = s["season_id"]
                # For extra leagues, store intervals
                self._extra_seasons.append({
                    "season_id": s["season_id"],
                    "league_id": s["league_id"],
                    "start": s["start_date"],
                    "end": s["end_date"]
                })

    async def _get_active_football_data_codes(self) -> set:
        """
        Retorna os football_data_code das leagues que possuem ao menos uma
        temporada ativa (is_current = TRUE). Leagues sem código são ignoradas.
        """
        await self._init_db_and_caches()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT l.name, l.country
                FROM seasons s
                JOIN leagues l ON s.league_id = l.league_id
                WHERE s.is_current = TRUE
                """
            )

        active_codes = set()
        for row in rows:
            for key, conf in self._leagues_config.items():
                if (conf.get("name") == row["name"]
                        and conf.get("country") == row["country"]
                        and conf.get("football_data_code")):
                    active_codes.add(conf["football_data_code"])

        logger.info("football_data_daily_active_codes", codes=sorted(active_codes))
        return active_codes

    async def health_check(self) -> bool:
        """Valida que o repositório principal está vivo efetuando um GET ultra rápido de um CSV leve."""
        test_url = MAIN_URL_TEMPLATE.format(season="2324", code="E0")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(test_url)
                if resp.status_code == 200:
                    text = resp.content.decode('utf-8', errors='ignore')
                    return text.startswith("Div,Date")
                return False
        except Exception as e:
            logger.error("health_check_failed", error=str(e))
            return False

    async def collect(self, mode: str = "seed-aliases", output_file: str = "output/team_aliases_seed.csv") -> CollectResult:
        """
        Orquestra a coleta dos CSVs configurados.
        mode:
          'seed-aliases'  -> Extrai times únicos e gera CSV. Não escreve no banco.
          'backfill'      -> Efetua parse, match resolution, e INSERTs definitivos (todas as seasons).
          'daily-update'  -> Igual ao backfill, mas APENAS para seasons com is_current = TRUE.
                             Silenciosamente ignora leagues sem football_data_code.
        """
        job_id = self.generate_job_id("batch_csv")
        await self._init_db_and_caches()

        # No modo daily-update, filtramos as leagues ativas no banco
        active_fd_codes: set | None = None
        if mode == "daily-update":
            active_fd_codes = await self._get_active_football_data_codes()
            if not active_fd_codes:
                logger.info("football_data_daily_no_active_leagues")
                return CollectResult(
                    source=self.source_name,
                    job_type="batch_csv",
                    job_id=job_id,
                    status=CollectStatus.SUCCESS,
                    started_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc),
                    records=[],
                    records_collected=0,
                )

        tasks = []
        urls_meta = []

        for l_key, conf in self._leagues_config.items():
            code = conf.get("football_data_code")
            if not code:
                continue  # Liga sem código CSV — ignorar silenciosamente

            # No modo daily-update: pular leagues de temporadas inativas
            if active_fd_codes is not None and code not in active_fd_codes:
                continue

            l_type = conf.get("football_data_type", "main")
            if l_type == "main":
                for s_key, s_data in conf.get("seasons", {}).items():
                    fd_season = s_data.get("fd")
                    if fd_season:
                        url = MAIN_URL_TEMPLATE.format(season=fd_season, code=code)
                        urls_meta.append({'url': url, 'type': 'main', 'code': code, 'fd_season': fd_season})
            else:
                url = EXTRA_URL_TEMPLATE.format(code=code)
                urls_meta.append({'url': url, 'type': 'extra', 'code': code})

        # Parallelismo limitado
        sem = asyncio.Semaphore(10)

        # No daily-update, o modo de insert é igual ao backfill
        effective_mode = "backfill" if mode == "daily-update" else mode

        async def _download_and_parse(meta: dict):
            async with sem:
                return await self._process_url(meta, effective_mode)

        logger.info("football_data_start", urls_count=len(urls_meta), mode=mode)
        results = await asyncio.gather(*[_download_and_parse(m) for m in urls_meta], return_exceptions=True)

        aliases_set = set()
        total_matches = 0
        failed_downloads = 0

        for r in results:
            if isinstance(r, Exception):
                logger.error("football_data_download_error", error=str(r))
                failed_downloads += 1
            elif r:
                if effective_mode == "seed-aliases":
                    aliases_set.update(r)
                else:
                    total_matches += r

        if effective_mode == "seed-aliases":
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            df_aliases = pd.DataFrame(sorted(list(aliases_set)), columns=["football_data_name"])
            df_aliases["canonical_name_bet365"] = ""
            df_aliases["country"] = ""
            df_aliases["league_code"] = ""
            df_aliases.to_csv(output_file, index=False)
            logger.info("aliases_seed_generated", count=len(aliases_set), path=output_file)

        return CollectResult(
            source=self.source_name,
            job_type="batch_csv",
            job_id=job_id,
            status=CollectStatus.SUCCESS if failed_downloads == 0 else CollectStatus.PARTIAL,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            records=[],
            records_collected=total_matches if effective_mode != "seed-aliases" else len(aliases_set),
        )

    async def _process_url(self, meta: dict, mode: str):
        url = meta['url']
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                raw_bytes = resp.content
        except httpx.HTTPError as e:
            logger.warning("http_error", url=url, error=str(e))
            return None

        # Conta linhas brutas
        raw_lines = raw_bytes.count(b'\n')
        
        # O Pandas tenta adivinhar o encoding, mas football-data as vezes usa Win-1252
        try:
            df = pd.read_csv(io.BytesIO(raw_bytes), encoding='utf-8', on_bad_lines='skip')
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(raw_bytes), encoding='latin-1', on_bad_lines='skip')

        parsed_lines = len(df)
        if parsed_lines < raw_lines - 2:
            # -2 devido ao trailing newline e o cabeçalho
            diff = max(0, raw_lines - 1 - parsed_lines)
            if diff > 0:
                logger.warning("bad_lines_skipped", url=url, skip_count=diff)

        # Normaliza colunas do formato "extra" para o formato "main"
        # Extra CSVs usam Home/Away/HG/AG/Res ao invés de HomeTeam/AwayTeam/FTHG/FTAG/FTR
        if meta.get('type') == 'extra':
            rename_map = {
                'Home': 'HomeTeam',
                'Away': 'AwayTeam',
                'HG': 'FTHG',
                'AG': 'FTAG',
                'Res': 'FTR',
            }
            df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        if df.empty or 'HomeTeam' not in df.columns or 'AwayTeam' not in df.columns:
            return set() if mode == 'seed-aliases' else 0

        # Uniformiza colunas de closing odds (garante existência)
        closing_cols = [
            'B365CH', 'B365CD', 'B365CA', 'B365C>2.5', 'B365C<2.5',
            'PSCH', 'PSCD', 'PSCA', 'PC>2.5', 'PC<2.5',
            'BFECH', 'BFECD', 'BFECA', 'BFEC>2.5', 'BFEC<2.5',
            # Extra leagues (não têm colunas 'C', usam as normais = closing)
            'B365H', 'B365D', 'B365A', 'B365>2.5', 'B365<2.5',
            'PSH', 'PSD', 'PSA', 'P>2.5', 'P<2.5',
            'BFH', 'BFD', 'BFA',
        ]
        for b_col in closing_cols:
            if b_col not in df.columns:
                df[b_col] = None

        if mode == "seed-aliases":
            return set(df['HomeTeam'].dropna().unique()).union(set(df['AwayTeam'].dropna().unique()))
        
        return await self._insert_matches_and_odds(df, meta)

    async def _insert_matches_and_odds(self, df: pd.DataFrame, meta: dict) -> int:
        await TeamResolver.load_cache()

        # Tratar Datas e kickoffs
        df = df.dropna(subset=['Date', 'HomeTeam', 'AwayTeam'])
        
        # Formatos flutuantes: dayfirst resolve europeu
        df['parsed_date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        if 'Time' not in df.columns:
            df['Time'] = '12:00'
        df['Time'] = df['Time'].fillna('12:00')
        
        df['kickoff_str'] = df['parsed_date'].dt.strftime('%Y-%m-%d') + ' ' + df['Time']
        df['kickoff'] = pd.to_datetime(df['kickoff_str'], errors='coerce')
        # Seta como UTC. Assumimos UTC para manter a sanidade (a Footystats vai consertar isso depois)
        df['kickoff'] = df['kickoff'].dt.tz_localize('UTC')

        league_id = self._league_map.get(meta['code'])
        if not league_id:
            logger.warning("league_id_not_found", code=meta['code'])
            return 0

        inserted_count = 0

        # Vamos iterar de forma sequencial ou batch assíncrono. Sendo poucas linhas, o overhead de conexões manda = batch local.
        async with self._pool.acquire() as conn:
            for idx, row in df.iterrows():
                if pd.isna(row['kickoff']):
                    continue
                
                kickoff_dt = row['kickoff']
                
                # Resolução de times
                home_id = await TeamResolver.resolve(self.source_name, str(row['HomeTeam']))
                away_id = await TeamResolver.resolve(self.source_name, str(row['AwayTeam']))

                if not home_id or not away_id:
                    # Time nao resolvido (esperado se a planilha de aliases não estiver 100% preenchida)
                    continue

                # Resolução de season_id
                season_id = None
                if meta['type'] == 'main':
                    season_id = self._season_map.get((league_id, meta['fd_season']))
                else:
                    # Extra leagues: buscar por range de data
                    d_obj = kickoff_dt.date()
                    for s_cfg in self._extra_seasons:
                        if s_cfg['league_id'] == league_id:
                            start = s_cfg['start']
                            end = s_cfg['end']
                            if start <= d_obj <= end:
                                season_id = s_cfg['season_id']
                                break
                
                if not season_id:
                    continue  # Safely ignore matches outside registered seasons

                # Inserir ou recuperar Match
                # Como é um script de semente (e depois corrigido por odds API), inseriremos se faltar
                match_id = await MatchResolver.resolve(
                    league_id=league_id, home_name=str(row['HomeTeam']), away_name=str(row['AwayTeam']),
                    kickoff_date=kickoff_dt.date(), source=self.source_name
                )
                
                if not match_id:
                    status = 'finished'
                    ft_home = int(row['FTHG']) if pd.notna(row.get('FTHG')) else None
                    ft_away = int(row['FTAG']) if pd.notna(row.get('FTAG')) else None
                    match_id = await conn.fetchval(
                        """
                        INSERT INTO matches (
                            season_id, league_id, home_team_id, away_team_id, 
                            kickoff, status, ft_home, ft_away, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                        RETURNING match_id
                        """,
                        season_id, league_id, home_id, away_id, kickoff_dt, status, ft_home, ft_away
                    )

                inserted_count += 1

                # ===========================================================
                # Inserção de Closing Odds (football-data.co.uk)
                # Main leagues: colunas com 'C' (B365CH, PSCH, BFECH...)
                # Extra leagues: colunas normais já são closing
                # ===========================================================
                pin_id = self._bookmaker_ids.get('pinnacle')
                bet_id = self._bookmaker_ids.get('bet365')
                bfe_id = self._bookmaker_ids.get('betfair_ex')

                def parse_odd(val):
                    return float(val) if pd.notna(val) and val != "" else None

                is_extra = meta.get('type') == 'extra'

                # --- 1. Bet365 1x2 Closing ---
                b1 = parse_odd(row.get('B365H' if is_extra else 'B365CH'))
                bx = parse_odd(row.get('B365D' if is_extra else 'B365CD'))
                b2 = parse_odd(row.get('B365A' if is_extra else 'B365CA'))
                if b1 and bx and b2:
                    await insert_odds_if_new(
                        conn=conn, match_id=match_id, bookmaker_id=bet_id, market_type='1x2',
                        line=None, period='ft', odds_1=b1, odds_x=bx, odds_2=b2,
                        source=self.source_name, collect_job_id='fd_closing',
                        is_closing=True, time=kickoff_dt
                    )

                # --- 2. Bet365 OU 2.5 Closing ---
                b_over = parse_odd(row.get('B365>2.5' if is_extra else 'B365C>2.5'))
                b_under = parse_odd(row.get('B365<2.5' if is_extra else 'B365C<2.5'))
                if b_over and b_under:
                    await insert_odds_if_new(
                        conn=conn, match_id=match_id, bookmaker_id=bet_id, market_type='ou',
                        line=2.5, period='ft', odds_1=b_over, odds_x=None, odds_2=b_under,
                        source=self.source_name, collect_job_id='fd_closing',
                        is_closing=True, time=kickoff_dt
                    )

                # --- 3. Pinnacle 1x2 Closing ---
                p1 = parse_odd(row.get('PSH' if is_extra else 'PSCH'))
                px = parse_odd(row.get('PSD' if is_extra else 'PSCD'))
                p2 = parse_odd(row.get('PSA' if is_extra else 'PSCA'))
                if p1 and px and p2:
                    await insert_odds_if_new(
                        conn=conn, match_id=match_id, bookmaker_id=pin_id, market_type='1x2',
                        line=None, period='ft', odds_1=p1, odds_x=px, odds_2=p2,
                        source=self.source_name, collect_job_id='fd_closing',
                        is_closing=True, time=kickoff_dt
                    )

                # --- 4. Pinnacle OU 2.5 Closing ---
                p_over = parse_odd(row.get('P>2.5' if is_extra else 'PC>2.5'))
                p_under = parse_odd(row.get('P<2.5' if is_extra else 'PC<2.5'))
                if p_over and p_under:
                    await insert_odds_if_new(
                        conn=conn, match_id=match_id, bookmaker_id=pin_id, market_type='ou',
                        line=2.5, period='ft', odds_1=p_over, odds_x=None, odds_2=p_under,
                        source=self.source_name, collect_job_id='fd_closing',
                        is_closing=True, time=kickoff_dt
                    )

                # --- 5. Betfair Exchange 1x2 Closing ---
                f1 = parse_odd(row.get('BFH' if is_extra else 'BFECH'))
                fx = parse_odd(row.get('BFD' if is_extra else 'BFECD'))
                f2 = parse_odd(row.get('BFA' if is_extra else 'BFECA'))
                if f1 and fx and f2 and bfe_id:
                    await insert_odds_if_new(
                        conn=conn, match_id=match_id, bookmaker_id=bfe_id, market_type='1x2',
                        line=None, period='ft', odds_1=f1, odds_x=fx, odds_2=f2,
                        source=self.source_name, collect_job_id='fd_closing',
                        is_closing=True, time=kickoff_dt
                    )

                # --- 6. Betfair Exchange OU 2.5 Closing ---
                f_over = parse_odd(row.get('BF>2.5' if is_extra else 'BFEC>2.5'))
                f_under = parse_odd(row.get('BF<2.5' if is_extra else 'BFEC<2.5'))
                if f_over and f_under and bfe_id:
                    await insert_odds_if_new(
                        conn=conn, match_id=match_id, bookmaker_id=bfe_id, market_type='ou',
                        line=2.5, period='ft', odds_1=f_over, odds_x=None, odds_2=f_under,
                        source=self.source_name, collect_job_id='fd_closing',
                        is_closing=True, time=kickoff_dt
                    )

        return inserted_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Football-Data.co.uk Collector")
    parser.add_argument("--mode", type=str, choices=["seed-aliases", "backfill"], default="seed-aliases")
    parser.add_argument("--output", type=str, default="output/team_aliases_seed.csv")
    args = parser.parse_args()

    collector = FootballDataCollector()
    result = asyncio.run(collector.collect(mode=args.mode, output_file=args.output))
    print(f"Execução concluída! Status: {result.status.name} | Processados: {result.records_collected}")
