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
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector
from src.normalizer.prematch_tracker import fetch_eligible_prematch_matches
from src.db.logger import configure_logging, get_logger

load_dotenv()
configure_logging()
logger = get_logger("run_prematch_tracker")

async def init_db():
    return await asyncpg.create_pool(
        user=os.getenv("DB_USER", "admin"),
        password=os.getenv("DB_PASS", "admin_password"),
        database=os.getenv("DB_NAME", "postgres"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

async def main():
    parser = argparse.ArgumentParser(description="Prematch Odds Tracker Flashscore")
    parser.add_argument("--phase", type=str, default="tracking_2x", help="Fase indicadora: tracking_2x, tracking_daily, tracking_4h, tracking_2h, pre30, pre2")
    parser.add_argument("--match_id", type=str, default=None, help="Processa apenas um match específico")
    parser.add_argument("--timeout-hours", type=float, default=2.5, help="Tempo máximo de execução (horas)")
    args = parser.parse_args()

    from src.alerts.telegram_mini import TelegramAlert
    await TelegramAlert.init()

    pool = await init_db()
    
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
                        inserted = await collector.collect_match(
                            browser, conn, 
                            str(match_uuid), fs_id, 
                            is_closing=False, 
                            job_id=f"prematch_{args.phase}",
                            is_prematch=True,
                            kickoff=kickoff
                        )
                        print(f"    -> Coleta concluida para {fs_id}. Snaps inseridos: {inserted}.")
                        total_collected += 1

                except Exception as e:
                    print(f"[ERROR] Falha severa no match {fs_id}. Erro: {e}")

                await asyncio.sleep(2)

            print(f"\n====== RESUMO PREMATCH TRACKER ======")
            print(f"Fase: {args.phase}")
            print(f"Partidas vistoriadas: {total_collected}")

            if total_collected > 0:
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
