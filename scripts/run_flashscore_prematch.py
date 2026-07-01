import asyncio
import os
import sys
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv
import asyncpg

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector, CollectionMetrics
from src.normalizer.prematch_tracker import fetch_eligible_prematch_matches
from src.db.logger import configure_logging, get_logger

load_dotenv()
configure_logging()
logger = get_logger("run_prematch_tracker")

from src.db.pool import get_pool

async def main():
    parser = argparse.ArgumentParser(description="Prematch Odds Tracker Flashscore")
    parser.add_argument("--phase", type=str, default="tracking_2x", help="Fase indicadora: tracking_2x, tracking_daily, tracking_4h, tracking_2h, pre30, pre2")
    parser.add_argument("--match_id", type=str, default=None, help="Processa apenas um match específico")
    parser.add_argument("--timeout-hours", type=float, default=2.5, help="Tempo máximo de execução (horas)")
    args = parser.parse_args()

    from src.alerts.telegram_mini import TelegramAlert
    await TelegramAlert.init()

    pool = await get_pool()
    
    try:
        async with pool.acquire() as conn:
            if args.match_id:
                # Busca apenas esse jogo
                row = await conn.fetchrow(
                    "SELECT match_id, flashscore_id, kickoff FROM matches WHERE match_id = $1 AND flashscore_id IS NOT NULL", 
                    args.match_id
                )
                matches = [{"match_id": row['match_id'], "flashscore_id": row['flashscore_id'], "kickoff": row['kickoff']}] if row else []
            else:
                if args.phase == "tracking_2x":
                    try:
                        # 1. Obter todas as ligas ativas com temporada atual
                        active_leagues = await conn.fetch("""
                            SELECT l.league_id, l.code, l.flashscore_path, l.last_fixtures_discovery_at
                            FROM leagues l
                            JOIN seasons s ON s.league_id = l.league_id
                            WHERE l.is_active = TRUE AND s.is_current = TRUE
                            ORDER BY l.league_id ASC
                        """)
                        
                        if active_leagues:
                            # 2. Dividir em 2 clusters usando o dia do ano
                            day_of_year = datetime.now().timetuple().tm_yday
                            active_cluster = []
                            for idx, l in enumerate(active_leagues):
                                # Cluster A (dia par): idx % 2 == 0
                                # Cluster B (dia ímpar): idx % 2 == 1
                                if (day_of_year % 2 == 0 and idx % 2 == 0) or (day_of_year % 2 != 0 and idx % 2 != 0):
                                    active_cluster.append(l)
                            
                            # 3. Montar target_urls para o discovery (apenas se não rodou nas últimas 40h)
                            from src.collectors.flashscore.discovery import FlashscoreDiscovery
                            from src.collectors.flashscore.config import LEAGUE_FLASHSCORE_PATHS
                            
                            discovery = FlashscoreDiscovery()
                            target_urls = {}
                            for l in active_cluster:
                                code = l["code"]
                                last_run = l["last_fixtures_discovery_at"]
                                if last_run:
                                    if last_run.tzinfo is None:
                                        last_run = last_run.replace(tzinfo=timezone.utc)
                                    # Se rodou nas últimas 40 horas, pula para não repetir à toa
                                    if datetime.now(timezone.utc) - last_run < timedelta(hours=40):
                                        print(f"  -> Liga {code} já teve discovery nas últimas 40h (PULANDO).")
                                        continue
                                
                                base_path = l["flashscore_path"] or LEAGUE_FLASHSCORE_PATHS.get(code)
                                if base_path:
                                    target_urls[code] = [f"https://www.flashscore.com/{base_path}/fixtures/"]
                            
                            if target_urls:
                                print(f"\n[Cluster Discovery] Executando Fixtures Discovery para {len(target_urls)} ligas do Cluster do Dia...")
                                res = await discovery.collect(mode="fixtures", specific_leagues=list(target_urls.keys()), target_urls=target_urls)
                                print(f"[Cluster Discovery] Concluído! Matches associados: {res.records_new}")
                                
                                # Atualiza a data do discovery no DB
                                for code in target_urls.keys():
                                    await conn.execute(
                                        "UPDATE leagues SET last_fixtures_discovery_at = NOW() WHERE code = $1", code
                                    )
                            else:
                                print("\n[Cluster Discovery] Nenhuma liga elegível necessita de discovery hoje.")
                    except Exception as e:
                        print(f"\n[Cluster Discovery] Falha ao rodar discovery no cluster do dia: {e}")
                        logger.error("prematch_cluster_discovery_failed", error=str(e))

                matches = await fetch_eligible_prematch_matches(conn, phase=args.phase)
            
        if not matches:
            print(f"\n[Prematch Tracking] Nenhuma partida pendente para a fase {args.phase}.")
            return

        print(f"\n[Prematch Tracking] {len(matches)} partidas encontradas para {args.phase}. Inicializando scraper...\n")

        collector = FlashscoreOddsCollector()

        async with AsyncCamoufox(
            headless=False,
            enable_cache=True
        ) as browser:
            total_collected = 0
            
            start_time = datetime.now()
            max_duration = timedelta(hours=args.timeout_hours)
            
            metrics = CollectionMetrics()
            
            for idx, m in enumerate(matches):
                if datetime.now() - start_time > max_duration:
                    print(f"\n[TIMEOUT] Limite de {args.timeout_hours}h atingido. Interrompendo prematch suavemente.")
                    break
                    
                match_uuid = m["match_id"]
                fs_id = m["flashscore_id"]
                kickoff = m["kickoff"]

                print(f"==> Processando {idx+1}/{len(matches)}: Flashscore ID {fs_id} (DB: {match_uuid})")

                try:
                    async with pool.acquire() as conn:
                        metrics.total_processed += 1
                        result = await collector.collect_match(
                            browser, conn, 
                            str(match_uuid), fs_id, 
                            is_closing=False, 
                            job_id=f"prematch_{args.phase}",
                            metrics=metrics,
                            is_prematch=True,
                            kickoff=kickoff
                        )
                        inserted = result["total_inserted"]
                        if inserted > 0:
                            metrics.with_odds += 1
                        print(f"    -> Coleta concluida para {fs_id}. Snaps inseridos: {inserted}.")
                        total_collected += 1

                except Exception as e:
                    print(f"[ERROR] Falha severa no match {fs_id}. Erro: {e}")

                await asyncio.sleep(2)

            print(f"\n====== RESUMO PREMATCH TRACKER ======")
            print(f"Fase: {args.phase}")
            print(f"Partidas vistoriadas: {total_collected}")

            if total_collected > 0 and not args.match_id:
                safe_phase = args.phase.replace('_', r'\_')
                msg = f"📈 *Prematch Tracking Finalizado* ({safe_phase})\nPartidas vistoriadas: {total_collected}"
                TelegramAlert.fire("info", msg)

    finally:
        await pool.close()
        await asyncio.sleep(1)
        await TelegramAlert.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Tracker cancelado pelo usuário (KeyboardInterrupt).")
