"""
scripts/run_flashscore_backfill.py

Backfill de odds do Flashscore para qualquer liga da temporada atual.
Uso:
  python scripts/run_flashscore_backfill.py --league ENG_PL
  python scripts/run_flashscore_backfill.py --league ENG_PL --limit 100
  python scripts/run_flashscore_backfill.py                              # todas as ligas com flashscore_path
"""
import asyncio
import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv
import asyncpg

# Adiciona o diretório raiz ao PYTHONPATH para permitir imports do módulo src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar diretório de dados do Camoufox ANTES da importação principal
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector
from src.collectors.flashscore.config import LEAGUE_FLASHSCORE_PATHS
from src.db.logger import configure_logging, get_logger

load_dotenv()
configure_logging()
logger = get_logger("run_flashscore_backfill")

async def init_db():
    return await asyncpg.create_pool(
        user=os.getenv("DB_USER", "admin"),
        password=os.getenv("DB_PASS", "admin_password"),
        database=os.getenv("DB_NAME", "postgres"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

async def mark_match_as_scraped(pool, match_id: str):
    """Marca a partida como coletada para evitar repetição no backfill."""
    async with pool.acquire() as conn:
        try:
            await conn.execute("UPDATE matches SET scraping_flashscore = true WHERE match_id = $1", match_id)
        except asyncpg.exceptions.UndefinedColumnError:
            await conn.execute("ALTER TABLE matches ADD COLUMN IF NOT EXISTS scraping_flashscore boolean DEFAULT false;")
            await conn.execute("UPDATE matches SET scraping_flashscore = true WHERE match_id = $1", match_id)

async def get_target_matches(pool, league_code: str = None, limit: int = 380):
    """
    Busca partidas finalizadas com flashscore_id preenchido
    mas sem scraping_flashscore = true.
    Se league_code é None, busca de todas as ligas.
    """
    async with pool.acquire() as conn:
        # Garantir que a coluna existe
        await conn.execute("ALTER TABLE matches ADD COLUMN IF NOT EXISTS scraping_flashscore boolean DEFAULT false;")

        if league_code:
            # Diagnóstico
            c_total = await conn.fetchval(
                "SELECT count(*) FROM matches m JOIN leagues l ON m.league_id = l.league_id WHERE l.code = $1",
                league_code
            )
            c_ft = await conn.fetchval(
                "SELECT count(*) FROM matches m JOIN leagues l ON m.league_id = l.league_id WHERE l.code = $1 AND m.status = 'finished'",
                league_code
            )
            c_fs = await conn.fetchval(
                "SELECT count(*) FROM matches m JOIN leagues l ON m.league_id = l.league_id WHERE l.code = $1 AND m.status = 'finished' AND m.flashscore_id IS NOT NULL",
                league_code
            )
            c_done = await conn.fetchval(
                "SELECT count(*) FROM matches m JOIN leagues l ON m.league_id = l.league_id WHERE l.code = $1 AND m.status = 'finished' AND m.flashscore_id IS NOT NULL AND m.scraping_flashscore = true",
                league_code
            )
            print(f"[DIAGNÓSTICO] {league_code}:")
            print(f"  Partidas configuradas:    {c_total}")
            print(f"  Finalizadas:              {c_ft}")
            print(f"  Com flashscore_id:        {c_fs}")
            print(f"  Já coletadas (odds):      {c_done}")
            print(f"  Pendentes:                {c_fs - c_done}")

            rows = await conn.fetch("""
                SELECT m.match_id, m.flashscore_id, m.kickoff
                FROM matches m
                JOIN leagues l ON m.league_id = l.league_id
                WHERE l.code = $1
                  AND m.status = 'finished'
                  AND m.flashscore_id IS NOT NULL
                  AND (m.scraping_flashscore IS NULL OR m.scraping_flashscore = false)
                ORDER BY m.kickoff ASC
                LIMIT $2
            """, league_code, limit)
        else:
            rows = await conn.fetch("""
                SELECT m.match_id, m.flashscore_id, m.kickoff, l.code
                FROM matches m
                JOIN leagues l ON m.league_id = l.league_id
                WHERE m.status = 'finished'
                  AND m.flashscore_id IS NOT NULL
                  AND (m.scraping_flashscore IS NULL OR m.scraping_flashscore = false)
                ORDER BY m.kickoff ASC
                LIMIT $1
            """, limit)

        return rows

async def main():
    parser = argparse.ArgumentParser(description="Backfill Flashscore Odds")
    parser.add_argument("--league", type=str, default=None, help="Código da liga (ex: ENG_PL, BRA_SA). Se omitido, roda todas.")
    parser.add_argument("--limit", type=int, default=380, help="Máximo de partidas para processar (default: 380)")
    parser.add_argument("--timeout-hours", type=float, default=2.5, help="Tempo máximo de execução (horas)")
    args = parser.parse_args()

    if args.league and args.league not in LEAGUE_FLASHSCORE_PATHS:
        print(f"❌ Liga '{args.league}' não tem flashscore_path configurado.")
        print(f"Ligas disponíveis: {', '.join(sorted(LEAGUE_FLASHSCORE_PATHS.keys()))}")
        return

    from src.alerts.telegram_mini import TelegramAlert
    await TelegramAlert.init()

    pool = await init_db()
    
    try:
        matches = await get_target_matches(pool, league_code=args.league, limit=args.limit)
        if not matches:
            league_label = args.league or "todas as ligas"
            print(f"\n[Backfill Flashscore] Nenhuma partida pendente para {league_label}!")
            TelegramAlert.fire(
                "info",
                f"📭 *Backfill Flashscore*\n"
                f"Fila vazia — 0 partidas pendentes.\n"
                f"Liga: `{league_label}`\n"
                f"_Aguardando discovery popular novos flashscore\\_ids._"
            )
            print("Completados com sucesso:    0")
            return

        print(f"\n[Backfill Flashscore] {len(matches)} partidas encontradas. Inicializando scraper...\n")

        collector = FlashscoreOddsCollector()

        # Abre o navegador central
        async with AsyncCamoufox(
            headless=False,  # Deve rodar sob xvfb-run na VPS
            enable_cache=True
        ) as browser:
            total_collected = 0
            total_errors = 0
            
            start_time = datetime.now()
            from datetime import timedelta
            max_duration = timedelta(hours=args.timeout_hours)

            for idx, m in enumerate(matches):
                if datetime.now() - start_time > max_duration:
                    print(f"\n[TIMEOUT] Limite de {args.timeout_hours}h atingido. Interrompendo backfill suavemente.")
                    break
                match_uuid = m["match_id"]
                fs_id = m["flashscore_id"]
                league_label = m.get("code", args.league or "?")

                print(f"==> [{league_label}] Processando {idx+1}/{len(matches)}: Flashscore ID {fs_id} (DB: {match_uuid})")

                try:
                    async with pool.acquire() as conn:
                        inserted = await collector.collect_match(browser, conn, str(match_uuid), fs_id, is_closing=True, job_id=f"backfill_{league_label}")

                        print(f"    -> Coleta finalizada para {fs_id}. Odds Inseridas: {inserted}.")

                        await mark_match_as_scraped(pool, match_uuid)
                        total_collected += 1

                except Exception as e:
                    print(f"[ERROR] Falha severa no match {fs_id}. Erro: {e}")
                    total_errors += 1

                # Random wait para não explodir rate limit
                await asyncio.sleep(3)

            print(f"\n====== RESUMO BACKFILL ======")
            print(f"Liga:                       {args.league or 'TODAS'}")
            print(f"Completados com sucesso:    {total_collected}")
            print(f"Erros encontrados:          {total_errors}")

            if total_collected > 0:
                msg = f"Backfill Flashscore finalizado!\nLiga: {args.league or 'Múltiplas'}\nColetados: {total_collected}\nErros: {total_errors}"
                TelegramAlert.fire("info", msg)
            if total_errors > 0:
                TelegramAlert.fire("warning", f"Backfill Flashscore teve erros.\n{total_errors} jogos falharam nesta janela.")

    finally:
        await pool.close()
        # Ensure telegram sends out alerts
        await asyncio.sleep(1)
        await TelegramAlert.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Backfill cancelado pelo usuário (KeyboardInterrupt).")
