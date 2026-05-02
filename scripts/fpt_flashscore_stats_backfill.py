import os
import io
import asyncio
import argparse
from datetime import datetime
import pandas as pd
import requests

from src.db.pool import get_pool
from src.db.logger import get_logger
from src.normalizer.team_resolver import TeamResolver

logger = get_logger(__name__)

FPT_LEAGUE_MAP = {
    'ENG_PL': 'ENGLAND 1',
    'ENG_CH': 'ENGLAND 2',
    'ENG_L1': 'ENGLAND 3',
    'ENG_L2': 'ENGLAND 4',
    'ENG_NL': 'ENGLAND 5',
    'SCO_PL': 'SCOTLAND 1',
    'SCO_CH': 'SCOTLAND 2',
    'SCO_L1': 'SCOTLAND 3',
    'GER_BL': 'GERMANY 1',
    'GER_B2': 'GERMANY 2',
    'ITA_SA': 'ITALY 1',
    'ITA_SB': 'ITALY 2',
    'ESP_PD': 'SPAIN 1',
    'ESP_SD': 'SPAIN 2',
    'FRA_L1': 'FRANCE 1',
    'FRA_L2': 'FRANCE 2',
    'NED_ED': 'NETHERLANDS 1',
    'BEL_PL': 'BELGIUM 1',
    'POR_PL': 'PORTUGAL 1',
    'TUR_SL': 'TURKEY 1',
    'GRE_SL': 'GREECE 1',
    'BRA_SA': 'BRAZIL 1',
    'MEX_LM': 'MEXICO 1',
    'AUT_BL': 'AUSTRIA 1',
    'SWI_SL': 'SWITZERLAND 1',
}

class FPTStatsBackfill:
    def __init__(self):
        self.token = os.getenv("FPT_API_TOKEN")
        if not self.token:
            logger.error("FPT_API_TOKEN não encontrado no .env! Requisito obrigatório.")
            raise ValueError("FPT_API_TOKEN is missing")
        self.base_url = "https://api.futpythontrader.com/api/dados/bet365/download/"
        self.headers = {"Authorization": f"Token {self.token}"}
        self._pool = None

    async def _init_db(self):
        if self._pool is None:
            self._pool = await get_pool()
        await TeamResolver.load_cache()

    def _convert_season_label(self, label: str) -> str:
        return label

    def fetch_fpt_data(self, fpt_league: str, season: str) -> pd.DataFrame:
        params = {"league": fpt_league, "season": season}
        logger.info(f"Baixando FPT: League={fpt_league}, Season={season}")
        try:
            response = requests.get(self.base_url, headers=self.headers, params=params, timeout=60)
            if response.status_code == 200:
                df = pd.read_csv(io.BytesIO(response.content))
                logger.info(f"Download sucesso! Shape: {df.shape}")
                return df
            elif response.status_code == 403:
                logger.warning(f"Erro 403 Forbidden para {fpt_league}. Provavelmente restrito no plano gratuito.")
                return pd.DataFrame()
            else:
                logger.error(f"Erro HTTP {response.status_code} na API FPT: {response.text[:200]}")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Erro na requisição da FPT API: {e}")
            return pd.DataFrame()

    async def run(self, force_all: bool = False):
        await self._init_db()

        async with self._pool.acquire() as conn:
            # Identifica gaps ou pega todos
            if force_all:
                where_clause = ""
                logger.info("Modo FORCE ALL ativado: Buscando TODOS os matches com odds flashscore para update.")
            else:
                where_clause = "AND ms.xg_fs_home IS NULL"
                logger.info("Modo GAP ativado: Buscando apenas matches sem stats.")

            query_gaps = f"""
                SELECT DISTINCT l.code as league_code, s.label as season_label
                FROM matches m
                JOIN leagues l ON m.league_id = l.league_id
                JOIN seasons s ON m.season_id = s.season_id
                LEFT JOIN match_stats ms ON m.match_id = ms.match_id
                WHERE m.status = 'finished'
                  {where_clause}
                  AND EXISTS (
                      SELECT 1 FROM odds_history oh 
                      WHERE oh.match_id = m.match_id AND oh.source = 'flashscore'
                  )
            """
            gaps = await conn.fetch(query_gaps)
            if not gaps:
                logger.info("Nenhuma liga/temporada precisando de update encontrada!")
                return
            
            logger.info(f"Processando {len(gaps)} combinações de liga/temporada.")

            total_updated = 0

            for gap in gaps:
                league_code = gap['league_code']
                season_label = gap['season_label']
                
                fpt_league = FPT_LEAGUE_MAP.get(league_code)
                if not fpt_league:
                    logger.warning(f"Liga {league_code} não mapeada para FPT. Pulando.")
                    continue
                
                df = self.fetch_fpt_data(fpt_league, self._convert_season_label(season_label))
                if df.empty:
                    continue
                
                matches_db = await conn.fetch(f"""
                    SELECT m.match_id, m.kickoff::date as match_date, 
                           m.home_team_id, m.away_team_id
                    FROM matches m
                    JOIN leagues l ON m.league_id = l.league_id
                    JOIN seasons s ON m.season_id = s.season_id
                    LEFT JOIN match_stats ms ON m.match_id = ms.match_id
                    WHERE m.status = 'finished'
                      AND l.code = $1 AND s.label = $2
                      {where_clause}
                      AND EXISTS (
                          SELECT 1 FROM odds_history oh 
                          WHERE oh.match_id = m.match_id AND oh.source = 'flashscore'
                      )
                """, league_code, season_label)
                
                logger.info(f"[{league_code} - {season_label}] {len(matches_db)} jogos no DB precisando de stats.")

                required_cols = ['Date', 'Home', 'Away', 'xG_H_FT', 'xG_A_FT', 'xGOT_H_FT', 'xGOT_A_FT', 'xA_H_FT', 'xA_A_FT']
                missing_cols = [c for c in required_cols if c not in df.columns]
                if missing_cols:
                    logger.warning(f"FPT DataFrame ausente das colunas: {missing_cols}. Pulando temporada.")
                    continue
                
                df_filtered = df[required_cols]

                updates_to_run = []
                # Evitar requests concorrentes massivos para o BD, empacotar.
                for m_db in matches_db:
                    match_id = m_db['match_id']
                    db_date = str(m_db['match_date']) 
                    db_home_id = m_db['home_team_id']
                    db_away_id = m_db['away_team_id']
                    
                    df_day = df_filtered[df_filtered['Date'] == db_date]
                    if df_day.empty:
                        continue
                    
                    match_found = False
                    for _, row in df_day.iterrows():
                        fs_home = str(row['Home'])
                        fs_away = str(row['Away'])
                        
                        # Usa o resolve assíncrono para garantir que aliases desconhecidos
                        # sejam registrados na fila (_pending_unknowns) do TeamResolver.
                        home_id_fpt = await TeamResolver.resolve('fpt', fs_home)
                        away_id_fpt = await TeamResolver.resolve('fpt', fs_away)
                        
                        if home_id_fpt == db_home_id and away_id_fpt == db_away_id:
                            # Prepara nulos corretamente
                            def safe_float(v):
                                try:
                                    return float(v)
                                except:
                                    return None
                                    
                            upd = (
                                safe_float(row['xG_H_FT']),
                                safe_float(row['xG_A_FT']),
                                safe_float(row['xGOT_H_FT']),
                                safe_float(row['xGOT_A_FT']),
                                safe_float(row['xA_H_FT']),
                                safe_float(row['xA_A_FT']),
                                match_id
                            )
                            # Verifica se tem ao menos 1 stat válida
                            if any(x is not None for x in upd[:6]):
                                updates_to_run.append(upd)
                            match_found = True
                            break
                    
                    if not match_found:
                        pass # Alias faltante ou jogo não retornado pela FPT neste dia

                if updates_to_run:
                    # Roda o update em batch
                    await conn.executemany("""
                        UPDATE match_stats SET
                            xg_fs_home = COALESCE($1, xg_fs_home),
                            xg_fs_away = COALESCE($2, xg_fs_away),
                            xgot_fs_home = COALESCE($3, xgot_fs_home),
                            xgot_fs_away = COALESCE($4, xgot_fs_away),
                            xa_fs_home = COALESCE($5, xa_fs_home),
                            xa_fs_away = COALESCE($6, xa_fs_away),
                            collected_at = NOW()
                        WHERE match_id = $7
                    """, updates_to_run)
                    logger.info(f"[{league_code} - {season_label}] {len(updates_to_run)} matches atualizados!")
                    total_updated += len(updates_to_run)
                else:
                    logger.info(f"[{league_code} - {season_label}] Nenhum match processado/mapeado.")

            # Flush dos aliases desconhecidos encontrados no FPT/FootyStats
            unknowns_count = await TeamResolver.flush_unknowns()
            if unknowns_count > 0:
                logger.warning(f"{unknowns_count} aliases FPT desconhecidos foram enviados para a tabela unknown_aliases.")

            logger.info(f"Processo finalizado. Total de partidas atualizadas: {total_updated}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill de Flashscore stats via FutPythonTrader API")
    parser.add_argument("--force", action="store_true", help="Atualiza todas as stats, ignorando se já existem.")
    args = parser.parse_args()
    
    backfiller = FPTStatsBackfill()
    asyncio.run(backfiller.run(force_all=args.force))
