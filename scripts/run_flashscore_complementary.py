"""
scripts/run_flashscore_complementary.py

Script para raspar mercados faltantes (1x2_ft, btts, dc, dnb) e estatísticas 
em partidas que só tinham odd ah/ou do Flashscore.
Roda em lotes diários com limite de tempo (~2h25) usando uma fila via DB.
"""
import asyncio
import os
import sys
import argparse
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import asyncpg

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector
from src.db.logger import configure_logging, get_logger
from src.alerts.telegram_mini import TelegramAlert

load_dotenv()
configure_logging()
logger = get_logger("run_flashscore_complementary")

async def init_db():
    return await asyncpg.create_pool(
        user=os.getenv("DB_USER", "admin"),
        password=os.getenv("DB_PASS", "admin_password"),
        database=os.getenv("DB_NAME", "postgres"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

async def setup_queue(pool):
    """
    Cria a tabela de fila e insere as partidas faltantes restritas ao JSON inicial (idempotente).
    Garante que APENAS as partidas identificadas no escopo (ex: as 2.303 partidas iniciais)
    entrem na fila para esse processo complementar.
    """
    import json
    
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS fc_complementary_queue (
                match_id UUID PRIMARY KEY,
                flashscore_id VARCHAR(50),
                kickoff TIMESTAMP WITH TIME ZONE,
                status VARCHAR(20) DEFAULT 'pending',
                attempts INT DEFAULT 0,
                processed_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        # Popula a fila estritamente com base no arquivo JSON exportado (missing_matches_fs.json)
        json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "missing_matches_fs.json")
        inserted = 0
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                matches_to_insert = json.load(f)
                
            for match in matches_to_insert:
                try:
                    res = await conn.execute("""
                        INSERT INTO fc_complementary_queue (match_id, flashscore_id, kickoff)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (match_id) DO NOTHING;
                    """, match["match_id"], match["flashscore_id"], datetime.fromisoformat(match["kickoff"]) if match.get("kickoff") else None)
                    if res.endswith(" 1"):
                        inserted += 1
                except Exception as e:
                    logger.error(f"Failed to insert seed match {match['match_id']}: {e}")
            
            logger.info(f"[Queue Setup] Populated {inserted} new matches from JSON seed.")
        else:
            logger.warning(f"[Queue Setup] Seed file not found at {json_path}. Only processing existing queue items.")
        
        total = await conn.fetchval("SELECT count(*) FROM fc_complementary_queue")
        pending = await conn.fetchval("SELECT count(*) FROM fc_complementary_queue WHERE status = 'pending'")
        return total, pending

async def main():
    parser = argparse.ArgumentParser(description="Flashscore Complementary Rescrape (Missing Markets/Stats)")
    parser.add_argument("--limit", type=int, default=150, help="Máximo de partidas por rodada (default: 150)")
    parser.add_argument("--timeout-hours", type=float, default=2.41, help="Timeout em horas (default: 2.41 = ~2h25)")
    args = parser.parse_args()

    await TelegramAlert.init()
    pool = await init_db()

    try:
        total_q, pending_q = await setup_queue(pool)
        if pending_q == 0:
            logger.info("A fila FC Complementary Queue está vazia (0 pendentes). Nenhuma coleta a ser feita.")
            TelegramAlert.fire("info", "✅ *Rescrape Complementar Flashscore*\nFila 100% concluída. 0 pendentes.")
            return

        logger.info(f"Fila inicializada. Total: {total_q} | Pendentes antes da rodada: {pending_q}")

        # Busca lote de matches para esta rodada
        async with pool.acquire() as conn:
            matches = await conn.fetch("""
                SELECT match_id, flashscore_id, kickoff, attempts
                FROM fc_complementary_queue
                WHERE status IN ('pending', 'failed') AND attempts < 3
                ORDER BY kickoff DESC
                LIMIT $1
            """, args.limit)

        if not matches:
            logger.info("Nenhuma partida elegível no momento (tentativas esgotadas ou todas processadas).")
            return

        logger.info(f"Iniciando coleta complementar para {len(matches)} partidas (timeout: {args.timeout_hours}h)...")

        # Collector focado apenas nos mercados ausentes.
        # "1x2_ft", "1x2_ht", "btts", "dc", "dnb"
        markets = ["1x2_ft", "1x2_ht", "btts", "dc", "dnb"]
        collector = FlashscoreOddsCollector(markets=markets)

        total_collected = 0
        total_odds_inserted = 0
        total_successes = 0
        total_no_data = 0
        total_errors = 0

        start_time = datetime.now()
        max_duration = timedelta(hours=args.timeout_hours)

        async with AsyncCamoufox(headless=False, enable_cache=True) as browser:
            for idx, m in enumerate(matches):
                if datetime.now() - start_time > max_duration:
                    logger.warning(f"Timeout global de {args.timeout_hours}h atingido! Encerrando rodada graciosamente.")
                    break

                m_uuid = m["match_id"]
                fs_id = m["flashscore_id"]
                kickoff = m["kickoff"]
                attempts = m["attempts"]

                logger.info(f"==> Processando {idx+1}/{len(matches)}: Flashscore ID {fs_id} (Tentativa {attempts+1})")

                async with pool.acquire() as conn:
                    try:
                        # Chama a coleta explicitly permitindo collect_stats
                        inserted = await collector.collect_match(
                            browser, conn, 
                            str(m_uuid), fs_id, 
                            is_closing=True, 
                            job_id="fc_complementary_fix", 
                            skip_stats=False,
                            kickoff=kickoff
                        )

                        # Atualiza queue
                        status = 'success' if inserted > 0 else 'no_data'
                        if inserted > 0:
                            total_successes += 1
                        else:
                            total_no_data += 1
                        
                        total_odds_inserted += inserted
                        
                        await conn.execute("""
                            UPDATE fc_complementary_queue 
                            SET status = $1, attempts = attempts + 1, processed_at = NOW()
                            WHERE match_id = $2
                        """, status, m_uuid)
                        
                        logger.info(f"    -> Concluído {fs_id}: Inseridas {inserted} odds. Status: {status}")

                    except Exception as e:
                        logger.error(f"[ERROR] Falha severa no match {fs_id}. Erro: {e}")
                        total_errors += 1
                        await conn.execute("""
                            UPDATE fc_complementary_queue 
                            SET status = 'failed', attempts = attempts + 1, processed_at = NOW()
                            WHERE match_id = $1
                        """, m_uuid)

                total_collected += 1
                await asyncio.sleep(2)  # Delay conservador extra

        # Relatório de Rodada
        elapsed = datetime.now() - start_time
        
        async with pool.acquire() as conn:
            final_pending = await conn.fetchval("SELECT count(*) FROM fc_complementary_queue WHERE status IN ('pending', 'failed') AND attempts < 3")

        # Custo aproximado de rodadas restantes (assumindo ~total_collected por rodada)
        rounds_remaining = (final_pending // total_collected) + 1 if total_collected > 0 else "N/A"

        logger.info("=" * 40)
        logger.info("RESUMO DA RODADA COMPLEMENTAR")
        logger.info(f"Processadas: {total_collected}")
        logger.info(f"Sucessos (novos dados): {total_successes}")
        logger.info(f"Sem novos dados (no_data): {total_no_data}")
        logger.info(f"Erros encontrados: {total_errors}")
        logger.info(f"Odds Inseridas: {total_odds_inserted}")
        logger.info(f"Pendentes na Fila: {final_pending}")
        logger.info(f"Rodadas estimadas restantes: {rounds_remaining}")
        logger.info(f"Tempo total: {elapsed}")
        logger.info("=" * 40)

        msg = (
            f"🔄 *Resumo Rodada Complementar FS*\n"
            f"Processadas: {total_collected}\n"
            f"Sucessos: {total_successes} | No Data: {total_no_data} | Erros: {total_errors}\n"
            f"Odds Novas: {total_odds_inserted}\n"
            f"Pendentes restando: {final_pending}\n"
            f"Estimativa de rodadas: ~{rounds_remaining}\n"
            f"Duração: {str(elapsed).split('.')[0]}"
        )
        TelegramAlert.fire("info", msg)

    finally:
        await pool.close()
        await asyncio.sleep(1)
        await TelegramAlert.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Execução cancelada pelo usuário.")
