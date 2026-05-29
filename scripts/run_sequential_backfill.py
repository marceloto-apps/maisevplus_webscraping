"""
scripts/run_sequential_backfill.py

Backfill sequencial de odds e estatísticas do Flashscore para ligas cuja fonte primária é o Flashscore.
Processa liga por liga, temporada por temporada (da mais antiga para a mais atual),
garantindo throttling e rotação de sessão do Camoufox.
"""
import asyncio
import os
import sys
import argparse
import random
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar diretório de dados do Camoufox ANTES de qualquer importação
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.discovery import FlashscoreDiscovery
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector, CollectionMetrics
from src.collectors.flashscore.config import LEAGUE_FLASHSCORE_PATHS
from src.db.pool import get_pool
from src.db.logger import configure_logging, get_logger

# Throttling — ajustar conforme observação de rate limiting
DELAY_BETWEEN_REQUESTS_MIN = 2.0   # segundos
DELAY_BETWEEN_REQUESTS_MAX = 5.0   # segundos (aleatório no range)
DELAY_BETWEEN_SEASONS      = 30.0  # segundos
DELAY_BETWEEN_LEAGUES      = 180.0 # segundos (3 min)
MAX_REQUESTS_PER_SESSION   = 100   # rotacionar sessão Camoufox após N requisições

load_dotenv()
configure_logging()
logger = get_logger("run_sequential_backfill")


def build_flashscore_season_slug(label: str) -> str:
    """Converte label de temporada para slug de URL do Flashscore."""
    if "/" in label:
        parts = label.split("/")
        p1, p2 = parts[0].strip(), parts[1].strip()
        y1 = f"20{p1}" if len(p1) == 2 else p1
        y2 = f"20{p2}" if len(p2) == 2 else p2
        return f"{y1}-{y2}"
    return label


class BrowserManager:
    """Gerencia a sessão Camoufox com rotação automática baseada em requisições."""
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.request_count = 0

    async def get_browser(self):
        if self.browser is None or self.request_count >= MAX_REQUESTS_PER_SESSION:
            await self.close()
            logger.info(f"[Camoufox] Iniciando nova sessão de browser (Headless={self.headless})...")
            self.browser = await AsyncCamoufox(
                headless=self.headless,
                enable_cache=True
            ).__aenter__()
            self.request_count = 0
        return self.browser

    def increment_requests(self, count: int = 1):
        self.request_count += count
        logger.debug(f"[Camoufox] Requisições nesta sessão: {self.request_count}/{MAX_REQUESTS_PER_SESSION}")

    async def close(self):
        if self.browser is not None:
            logger.info("[Camoufox] Fechando sessão atual de browser...")
            try:
                await self.browser.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"[Camoufox] Erro ao fechar browser: {e}")
            self.browser = None
            self.request_count = 0


async def mark_match_as_scraped(pool, match_id: str):
    """Marca a partida como coletada para evitar repetição no backfill de odds/stats."""
    async with pool.acquire() as conn:
        await conn.execute("UPDATE matches SET scraping_flashscore = TRUE WHERE match_id = $1", match_id)


async def main():
    parser = argparse.ArgumentParser(description="Flashscore Sequential Backfill")
    parser.add_argument(
        "--leagues", nargs="*", default=None,
        help="Ligas específicas (ex: ARG_LP). Se omitido, roda todas com primary_source = 'flashscore'."
    )
    parser.add_argument(
        "--headless", action="store_true", default=False,
        help="Rodar o navegador em modo headless."
    )
    parser.add_argument(
        "--limit-matches", type=int, default=999999,
        help="Limite de partidas para processar por temporada."
    )
    parser.add_argument(
        "--timeout-hours", type=float, default=999999.0,
        help="Tempo máximo de execução em horas."
    )
    args = parser.parse_args()

    from src.alerts.telegram_mini import TelegramAlert
    await TelegramAlert.init()

    logger.info("=" * 70)
    logger.info("  INICIANDO BACKFILL SEQUENCIAL FLASHSCORE")
    logger.info("=" * 70)

    start_time = datetime.now()
    from datetime import timedelta
    max_duration = timedelta(hours=args.timeout_hours)

    pool = await get_pool()
    browser_mgr = BrowserManager(headless=args.headless)
    
    # Instancia collectors
    discovery = FlashscoreDiscovery()
    collector = FlashscoreOddsCollector()
    metrics = CollectionMetrics()
    task_summary = {}

    try:
        async with pool.acquire() as conn:
            # 1. Obter ligas elegíveis
            if args.leagues:
                leagues = await conn.fetch("""
                    SELECT league_id, code, name, country, flashscore_path, primary_source
                    FROM leagues
                    WHERE code = ANY($1) AND is_active = TRUE
                """, args.leagues)
            else:
                leagues = await conn.fetch("""
                    SELECT league_id, code, name, country, flashscore_path, primary_source
                    FROM leagues
                    WHERE primary_source = 'flashscore' AND is_active = TRUE
                """)

        if not leagues:
            logger.info("Nenhuma liga encontrada para processar.")
            return

        # 2. Obter todas as temporadas de todas as ligas elegíveis e filtrar as históricas concluídas
        tasks = []
        for league in leagues:
            league_id = league["league_id"]
            league_code = league["code"]
            async with pool.acquire() as conn:
                seasons = await conn.fetch("""
                    SELECT season_id, label, is_current
                    FROM seasons
                    WHERE league_id = $1
                """, league_id)
            for season in seasons:
                season_id = season["season_id"]
                label = season["label"]
                is_current = season["is_current"]

                # Para temporadas históricas, verificar se podemos pular definitivamente
                if not is_current:
                    async with pool.acquire() as conn:
                        # Total de partidas cadastradas no banco para esta temporada
                        total_matches = await conn.fetchval(
                            "SELECT COUNT(*) FROM matches WHERE season_id = $1", 
                            season_id
                        )
                        # Partidas que estão pendentes de scraping do Flashscore (odds/stats)
                        pending_matches = await conn.fetchval("""
                            SELECT COUNT(*)
                            FROM matches m
                            WHERE m.season_id = $1
                              AND m.status = 'finished'
                              AND m.flashscore_id IS NOT NULL
                              AND (m.scraping_flashscore IS NULL OR m.scraping_flashscore = FALSE)
                              AND (m.flashscore_stats_collected = FALSE OR m.flashscore_odds_collected = FALSE)
                        """, season_id)
                        # Aliases pendentes para esta liga (source = 'flashscore' e resolved = FALSE)
                        unresolved_aliases = await conn.fetchval("""
                            SELECT COUNT(*) 
                            FROM unknown_aliases 
                            WHERE source = 'flashscore' 
                              AND resolved = FALSE 
                              AND league_code = $1
                        """, league_code)

                    # Se já possui partidas, todas coletadas e não há aliases pendentes para a liga
                    if total_matches > 0 and pending_matches == 0 and unresolved_aliases == 0:
                        logger.info(
                            f"[ARCHIVED] Liga {league_code} | Temporada {label} "
                            f"completada (partidas: {total_matches}, pendentes: {pending_matches}, "
                            f"aliases não resolvidos: {unresolved_aliases}). Pulando definitivamente."
                        )
                        continue

                tasks.append((league, season))

        if not tasks:
            logger.info("Nenhuma temporada encontrada para processar.")
            return

        # Ordenar as tarefas priorizando temporadas atuais (is_current = True) de todas as ligas
        # seguindo preferred_order das ligas. Depois as históricas (is_current = False) por preferred_order
        # e mais recentes (ano decrescente).
        preferred_order = ["ARG_LP", "CHI_LDP", "USA_MLS", "BRA_SB", "NOR_ELI", "JPN_J1", "SWE_ALL", "FIN_VEI", "CHN_SL"]
        
        def task_sort_key(item):
            lg, se = item
            code = lg["code"]
            is_cur = se["is_current"]
            lbl = se["label"]
            
            current_priority = 0 if is_cur else 1
            
            if code in preferred_order:
                league_priority = preferred_order.index(code)
            else:
                league_priority = len(preferred_order) + 1
                
            try:
                if "/" in lbl:
                    year = int(lbl.split("/")[0])
                else:
                    year = int(lbl)
            except:
                year = 0
            year_priority = -year
            
            return (current_priority, league_priority, year_priority)

        tasks = sorted(tasks, key=task_sort_key)

        for idx_t, (league, season) in enumerate(tasks):
            if datetime.now() - start_time > max_duration:
                logger.info(f"[TIMEOUT] Limite de {args.timeout_hours}h atingido. Interrompendo backfill sequencial.")
                break

            league_id = league["league_id"]
            league_code = league["code"]
            flashscore_path = league["flashscore_path"]
            primary_source = league["primary_source"]

            season_id = season["season_id"]
            label = season["label"]
            is_current = season["is_current"]

            logger.info(f"\n[TASK] [{idx_t+1}/{len(tasks)}] Processando: {league_code} | Temporada: {label} (Current: {is_current})")
            
            if not flashscore_path:
                logger.warning(f"  [WARN] Liga {league_code} não tem flashscore_path definido. Pulando.")
                continue

            work_done = False

            # A. Executar Discovery para a temporada (pula se for histórica e já possuir partidas)
            should_run_discovery = True
            if not is_current:
                async with pool.acquire() as conn:
                    existing_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM matches WHERE season_id = $1", 
                        season_id
                    )
                if existing_count > 0:
                    logger.info(f"    -> Discovery pulado: Temporada histórica '{label}' já possui {existing_count} partidas no banco.")
                    should_run_discovery = False

            if should_run_discovery:
                # Constrói URL do Discovery para esta temporada
                if is_current:
                    season_url = f"https://www.flashscore.com/{flashscore_path}/results/"
                else:
                    season_slug = build_flashscore_season_slug(label)
                    season_url = f"https://www.flashscore.com/{flashscore_path}-{season_slug}/results/"

                logger.info(f"    -> Iniciando Discovery na URL: {season_url}")
                try:
                    # O Discovery gerencia seu próprio browser e encerra-o internamente.
                    res_disc = await discovery.collect(
                        mode="results",
                        specific_leagues=[league_code],
                        target_urls={league_code: [season_url]}
                    )
                    logger.info(f"    -> Discovery finalizado. Matches associados/inseridos: {res_disc.records_new}")
                    work_done = True
                except Exception as e:
                    logger.error(f"    [ERROR] Falha na descoberta de partidas para {league_code} {label}: {e}")

                # Throttling após o request de discovery
                delay = random.uniform(DELAY_BETWEEN_REQUESTS_MIN, DELAY_BETWEEN_REQUESTS_MAX)
                logger.debug(f"    Aguardando {delay:.2f}s (throttling)...")
                await asyncio.sleep(delay)

            # B. Obter partidas finalizadas pendentes de odds/stats nesta temporada
            async with pool.acquire() as conn:
                # Garantir que a coluna de controle exista
                await conn.execute("ALTER TABLE matches ADD COLUMN IF NOT EXISTS scraping_flashscore BOOLEAN DEFAULT FALSE;")
                
                matches = await conn.fetch("""
                    SELECT m.match_id, m.flashscore_id, m.kickoff
                    FROM matches m
                    WHERE m.season_id = $1
                      AND m.status = 'finished'
                      AND m.flashscore_id IS NOT NULL
                      AND (m.scraping_flashscore IS NULL OR m.scraping_flashscore = FALSE)
                      AND (m.flashscore_stats_collected = FALSE OR m.flashscore_odds_collected = FALSE)
                    ORDER BY m.kickoff DESC
                    LIMIT $2
                """, season_id, args.limit_matches)

            if not matches:
                logger.info("    -> Nenhuma partida pendente de odds/stats nesta temporada.")
            else:
                logger.info(f"    -> Encontradas {len(matches)} partidas pendentes. Iniciando coleta...")
                work_done = True
                
                for idx_m, match in enumerate(matches):
                    if datetime.now() - start_time > max_duration:
                        logger.info(f"      [TIMEOUT] Limite de {args.timeout_hours}h atingido. Interrompendo coleta de partidas.")
                        break
                    match_uuid = match["match_id"]
                    fs_id = match["flashscore_id"]
                    kickoff = match["kickoff"]

                    logger.info(f"      [{idx_m+1}/{len(matches)}] Partida {fs_id} | Kickoff: {kickoff}")

                    # Garante browser ativo e dentro do limite de requisições
                    browser = await browser_mgr.get_browser()
                    
                    try:
                        async with pool.acquire() as conn:
                            metrics.total_processed += 1
                            result = await collector.collect_match(
                                browser=browser,
                                conn=conn,
                                match_id_uuid=str(match_uuid),
                                flashscore_id=fs_id,
                                is_closing=True,
                                job_id=f"backfill_{league_code}_{label}",
                                metrics=metrics,
                                kickoff=kickoff
                            )
                            
                            inserted = result["total_inserted"]
                            logger.info(f"        Coletado: {inserted} odds inseridas.")

                            if inserted > 0:
                                metrics.with_odds += 1

                            if result["is_complete"]:
                                await mark_match_as_scraped(pool, match_uuid)
                                logger.info(f"        ✅ Partida {fs_id} marcada como concluída.")
                            else:
                                logger.warning(
                                    f"        ⚠️ Partida {fs_id} incompleta — coletados: {result['markets_collected']}, "
                                    f"faltando: {result['markets_failed']}."
                                )
                            
                            task_key = f"{league_code} {label}"
                            task_summary[task_key] = task_summary.get(task_key, 0) + 1

                    except Exception as e:
                        logger.error(f"        [ERROR] Erro na coleta da partida {fs_id}: {e}")

                    # Incrementa contador de requests e verifica se deve rotacionar
                    browser_mgr.increment_requests(1)

                    # Throttling entre partidas
                    delay = random.uniform(DELAY_BETWEEN_REQUESTS_MIN, DELAY_BETWEEN_REQUESTS_MAX)
                    logger.debug(f"        Aguardando {delay:.2f}s (throttling)...")
                    await asyncio.sleep(delay)

            # Delay de transição de temporada/liga (apenas se houve trabalho feito para evitar esperas inúteis)
            if work_done and idx_t < len(tasks) - 1:
                logger.info(f"  [DELAY] Aguardando {DELAY_BETWEEN_SEASONS}s para trocar de tarefa...")
                await asyncio.sleep(DELAY_BETWEEN_SEASONS)

        logger.info(f"Completados com sucesso: {metrics.with_odds}")
        print(f"Completados com sucesso: {metrics.with_odds}")
        
        if task_summary:
            print("=== RESUMO DE EXECUCAO ===")
            for task_key, count in task_summary.items():
                print(f"  - {task_key}: {count} partidas")

    finally:
        await browser_mgr.close()
        await pool.close()
        await TelegramAlert.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Backfill interrompido pelo usuário.")
