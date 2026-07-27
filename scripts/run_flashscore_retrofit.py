import asyncio
import os
import sys
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar diretório de dados do Camoufox ANTES de qualquer importação
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector, CollectionMetrics
from src.db.pool import get_pool
from src.db.logger import configure_logging, get_logger

load_dotenv()
configure_logging()
logger = get_logger("run_flashscore_retrofit")

async def main():
    parser = argparse.ArgumentParser(description="Flashscore Odds Retrofit Runner")
    parser.add_argument(
        "--league-id", type=int, default=None,
        help="ID de uma liga específica para forçar execução. Se omitido, pega a próxima da fila."
    )
    parser.add_argument(
        "--limit-matches", type=int, default=None,
        help="Limite de partidas para processar nesta execução (útil para testes)."
    )
    parser.add_argument(
        "--headless", action="store_true", default=False,
        help="Rodar navegador em modo headless."
    )
    args = parser.parse_args()

    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # Recuperar ligas que ficaram travadas no status 'running' por mais de 6 horas
        recovered = await conn.execute("""
            UPDATE retrofit_queue
            SET status = 'pending'
            WHERE status = 'running' AND last_attempt_at < NOW() - INTERVAL '6 hours'
        """)
        if recovered != "UPDATE 0":
            logger.info(f"Recuperadas ligas travadas em 'running': {recovered}")

        league_id = args.league_id
        
        # 1. Identificar qual liga processar
        if league_id is not None:
            # Forçar execução de uma liga específica
            league_row = await conn.fetchrow("""
                SELECT league_id, priority, status, attempts
                FROM retrofit_queue
                WHERE league_id = $1
            """, league_id)
            if not league_row:
                print(f"Liga ID {league_id} não encontrada na fila de retrofit!")
                # Criar entrada temporária na fila se não existir (para facilitar testes)
                await conn.execute("""
                    INSERT INTO retrofit_queue (league_id, priority, status, total_matches)
                    VALUES ($1, 999, 'pending', (SELECT COUNT(*) FROM matches WHERE league_id = $1 AND flashscore_id IS NOT NULL))
                    ON CONFLICT (league_id) DO NOTHING
                """, league_id)
                league_row = {"league_id": league_id, "attempts": 0}
        else:
            # Obter a próxima pendente ou falhada com attempts < 3
            league_row = await conn.fetchrow("""
                SELECT league_id, priority, status, attempts
                FROM retrofit_queue
                WHERE status = 'pending' OR (status = 'failed' AND attempts < 3)
                ORDER BY priority ASC
                LIMIT 1
            """)
            
        if not league_row:
            logger.info("Nenhuma liga pendente ou elegível para retrofit na fila.")
            print("Fila de retrofit concluída ou sem ligas elegíveis.")
            return

        league_id = league_row["league_id"]
        logger.info(f"Iniciando processamento de retrofit para a liga ID: {league_id}")
        
        # Incrementar tentativas e marcar como running
        await conn.execute("""
            UPDATE retrofit_queue
            SET status = 'running',
                last_attempt_at = NOW(),
                attempts = attempts + 1
            WHERE league_id = $1
        """, league_id)

    # 2. Buscar partidas elegíveis usando a query de reentrância CANÔNICA
    async with pool.acquire() as conn:
        matches = await conn.fetch("""
            SELECT m.match_id, m.flashscore_id, m.kickoff
            FROM matches m
            WHERE m.league_id = $1
              AND m.flashscore_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM odds_history o
                  WHERE o.match_id = m.match_id AND o.is_opening = TRUE
              )
              AND NOT EXISTS (
                  SELECT 1 FROM retrofit_match_log l
                  WHERE l.match_id = m.match_id AND l.status = 'no_opening'
              )
            ORDER BY m.kickoff
        """, league_id)
        
        total_eligible = len(matches)
        logger.info(f"Encontradas {total_eligible} partidas elegíveis para retrofit na liga {league_id}")

        if total_eligible == 0:
            logger.info(f"Sem partidas elegíveis restando. Completando liga {league_id} na fila.")
            await conn.execute("UPDATE retrofit_queue SET status = 'completed' WHERE league_id = $1", league_id)
            return

        # Aplicar limite de matches se solicitado
        if args.limit_matches is not None:
            matches = matches[:args.limit_matches]
            logger.info(f"Limitando execução para as primeiras {len(matches)} partidas")

    # 3. Processar em lotes de 50 para rotação de browser
    batch_size = 50
    matches_list = [dict(m) for m in matches]
    batches = [matches_list[i:i + batch_size] for i in range(0, len(matches_list), batch_size)]
    
    collector = FlashscoreOddsCollector(markets=["1x2_ft", "ou_ft", "ah_ft"])
    job_id = collector.generate_job_id("flashscore_retrofit")
    metrics = CollectionMetrics()
    
    success_matches = 0
    failed_matches = 0
    no_opening_matches = 0
    
    catastrophic_error = None
    
    try:
        for b_idx, batch in enumerate(batches):
            logger.info(f"Iniciando sub-lote {b_idx + 1}/{len(batches)} (Tamanho: {len(batch)} matches)")
            
            # Novo browser por sub-lote de 50
            async with AsyncCamoufox(headless=args.headless) as browser:
                for idx, m in enumerate(batch):
                    m_uuid = m["match_id"]
                    fs_id = m["flashscore_id"]
                    kickoff = m["kickoff"]
                    
                    logger.info(f"[{b_idx+1}/{len(batches)}] Retrofit match {idx+1}/{len(batch)} | FS ID: {fs_id}")
                    
                    has_opening = False
                    try:
                        # Executar coleta para esta partida única com conexão isolada
                        async with pool.acquire() as conn:
                            result = await collector.collect_match(
                                browser, conn, m_uuid, fs_id,
                                is_closing=False, job_id=job_id, metrics=metrics,
                                is_prematch=False, kickoff=kickoff, skip_stats=True,
                                skip_closing=True
                            )
                            
                            # Verificar se gravou opening odds no banco (is_opening = TRUE)
                            has_opening = await conn.fetchval("""
                                SELECT EXISTS (
                                    SELECT 1 FROM odds_history
                                    WHERE match_id = $1 AND is_opening = TRUE
                                )
                            """, m_uuid)
                            
                        # Atualiza estatísticas e log da partida em conexão dedicada
                        async with pool.acquire() as conn:
                            status = 'success' if has_opening else 'no_opening'
                            if has_opening:
                                success_matches += 1
                            else:
                                no_opening_matches += 1
                                
                            await conn.execute("""
                                INSERT INTO retrofit_match_log (match_id, league_id, status, error_message, processed_at)
                                VALUES ($1, $2, $3, NULL, NOW())
                                ON CONFLICT (match_id) DO UPDATE SET
                                    status = EXCLUDED.status,
                                    error_message = EXCLUDED.error_message,
                                    processed_at = NOW()
                            """, m_uuid, league_id, status)
                            
                            await conn.execute("""
                                UPDATE retrofit_queue
                                SET processed_matches = processed_matches + 1,
                                    success_matches = success_matches + $2
                                WHERE league_id = $1
                            """, league_id, 1 if has_opening else 0)
                            
                    except Exception as e:
                        logger.error(f"Falha ao processar match {fs_id}: {e}")
                        failed_matches += 1
                        # Gravar status como failed usando conexão nova e segura
                        try:
                            async with pool.acquire() as err_conn:
                                await err_conn.execute("""
                                    INSERT INTO retrofit_match_log (match_id, league_id, status, error_message, processed_at)
                                    VALUES ($1, $2, 'failed', $3, NOW())
                                    ON CONFLICT (match_id) DO UPDATE SET
                                        status = EXCLUDED.status,
                                        error_message = EXCLUDED.error_message,
                                        processed_at = NOW()
                                """, m_uuid, league_id, str(e)[:500])
                                
                                await err_conn.execute("""
                                    UPDATE retrofit_queue
                                    SET processed_matches = processed_matches + 1
                                    WHERE league_id = $1
                                """, league_id)
                        except Exception as log_err:
                            logger.error(f"Erro ao salvar retrofit_match_log de falha para {fs_id}: {log_err}")

                    # Respeitar rate limits
                    await asyncio.sleep(2.0)
            
            # Intervalo entre sub-lotes para resfriar
            if b_idx < len(batches) - 1:
                logger.info("Resfriando browser antes do próximo sub-lote...")
                await asyncio.sleep(10.0)
                
    except Exception as e:
        catastrophic_error = str(e)
        logger.exception(f"Erro catastrófico no runner de retrofit da liga {league_id}: {e}")

    # 4. Finalização e registro de status geral
    async with pool.acquire() as conn:
        if catastrophic_error:
            await conn.execute("""
                UPDATE retrofit_queue
                SET status = 'failed',
                    error_details = $2
                WHERE league_id = $1
            """, league_id, catastrophic_error)
        else:
            # Verificar se ainda sobram partidas elegíveis na liga
            remaining = await conn.fetchval("""
                SELECT COUNT(*)
                FROM matches m
                WHERE m.league_id = $1
                  AND m.flashscore_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM odds_history o
                      WHERE o.match_id = m.match_id AND o.is_opening = TRUE
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM retrofit_match_log l
                      WHERE l.match_id = m.match_id AND l.status = 'no_opening'
                  )
            """, league_id)
            
            if remaining == 0:
                logger.info(f"Todos os matches elegíveis da liga {league_id} foram concluídos.")
                await conn.execute("UPDATE retrofit_queue SET status = 'completed' WHERE league_id = $1", league_id)
            else:
                logger.info(f"Execução parcial concluída. {remaining} partidas ainda elegíveis na liga {league_id}. Voltando status para 'pending'.")
                await conn.execute("""
                    UPDATE retrofit_queue
                    SET status = 'pending',
                        attempts = 0
                    WHERE league_id = $1
                """, league_id)

        # 5. Salvar métricas de saúde da coleta (HealthMetrics)
        # Denominador de saúde = success_matches + failed_matches. no_opening não conta como falha.
        total_processed_health = success_matches + failed_matches
        success_rate = 100.0
        if total_processed_health > 0:
            success_rate = (success_matches / total_processed_health) * 100.0
            
        alert_level = '🟢' if success_rate >= 80.0 else '🔴'
        
        try:
            await conn.execute("""
                INSERT INTO scraping_health (
                    source, total_matches, matches_with_odds,
                    bet365_found, pinnacle_found, avg_bookmakers,
                    unidentified_rows, unknown_bookmakers, parse_errors,
                    success_rate, alert_level, job_id, opening_found
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """, 
            "flashscore_retrofit", total_processed_health, success_matches,
            metrics.bet365_found, metrics.pinnacle_found, metrics.avg_bookmakers,
            metrics.unidentified_rows, list(metrics.unknown_bookmakers), metrics.parse_errors,
            success_rate, alert_level, job_id, success_matches)
            
            logger.info(f"[Retrofit] HealthMetrics salvas: {success_rate:.1f}% success rate | Level: {alert_level.replace('🔴', 'RED').replace('🟢', 'GREEN')}")
        except Exception as she:
            logger.error(f"[Retrofit] Falha ao salvar scraping_health: {she}")

    print(f"\nRetrofit da liga {league_id} concluído:")
    print(f"- Sucesso (gravou opening): {success_matches}")
    print(f"- Sem opening no Flashscore (no_opening): {no_opening_matches}")
    print(f"- Erros (failed): {failed_matches}")

if __name__ == "__main__":
    asyncio.run(main())
