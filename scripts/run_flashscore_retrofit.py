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
        "--timeout-hours", type=float, default=2.5,
        help="Tempo máximo de execução em horas antes de encerrar graciosamente."
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
              AND m.kickoff <= NOW()
              AND NOT EXISTS (
                  SELECT 1 FROM odds_history o
                  WHERE o.match_id = m.match_id AND o.is_opening = TRUE
              )
              AND NOT EXISTS (
                  SELECT 1 FROM retrofit_match_log l
                  WHERE l.match_id = m.match_id AND l.status = 'no_opening'
              )
            ORDER BY m.kickoff DESC
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
    
    # ── Circuit breaker ──────────────────────────────────────────────
    # Se N partidas consecutivas retornarem 0 linhas de odds parseadas,
    # assume que o DOM mudou e aborta para não queimar partidas boas
    # com status 'no_opening' (definitivo/permanente).
    CIRCUIT_BREAKER_THRESHOLD = 10
    consecutive_empty = 0
    circuit_broken = False
    html_dumps_saved = 0
    MAX_HTML_DUMPS = 3  # salvar no máx 3 dumps de diagnóstico
    
    catastrophic_error = None
    
    from datetime import timedelta
    start_time = datetime.now(timezone.utc)
    max_duration = timedelta(hours=args.timeout_hours)
    timeout_reached = False

    try:
        for b_idx, batch in enumerate(batches):
            if timeout_reached or circuit_broken:
                break

            logger.info(f"Iniciando sub-lote {b_idx + 1}/{len(batches)} (Tamanho: {len(batch)} matches)")
            
            # Novo browser por sub-lote de 50
            async with AsyncCamoufox(headless=args.headless) as browser:
                for idx, m in enumerate(batch):
                    if datetime.now(timezone.utc) - start_time > max_duration:
                        logger.info(f"[Retrofit] Limite de tempo de {args.timeout_hours}h atingido. Encerrando lote graciosamente.")
                        timeout_reached = True
                        break

                    m_uuid = m["match_id"]
                    fs_id = m["flashscore_id"]
                    kickoff = m["kickoff"]
                    
                    logger.info(f"[{b_idx+1}/{len(batches)}] Retrofit match {idx+1}/{len(batch)} | FS ID: {fs_id}")
                    
                    has_opening = False
                    markets_ok   = []
                    markets_fail = []
                    inserted_count = 0
                    is_complete = False
                    try:
                        # Executar coleta para esta partida única com conexão isolada
                        async with pool.acquire() as conn:
                            result = await collector.collect_match(
                                browser, conn, m_uuid, fs_id,
                                is_closing=False, job_id=job_id, metrics=metrics,
                                is_prematch=False, kickoff=kickoff, skip_stats=True,
                                skip_closing=True
                            )
                            
                            # Log de diagnóstico granular — essencial para rastrear falhas silenciosas
                            markets_ok   = result.get("markets_collected", [])
                            markets_fail = result.get("markets_failed", [])
                            inserted_count = result.get("total_inserted", 0)
                            is_complete = result.get("is_complete", False)
                            diag_html   = result.get("debug_html")  # HTML bruto quando 0 odds extraídas
                            logger.info(
                                f"[Retrofit-Diag] {fs_id}: "
                                f"inserted={inserted_count}, "
                                f"markets_ok={markets_ok}, "
                                f"markets_fail={markets_fail}, "
                                f"complete={is_complete}"
                            )
                            
                            # Salvar HTML de diagnóstico para as primeiras falhas
                            if diag_html and html_dumps_saved < MAX_HTML_DUMPS:
                                import os as _os
                                dump_dir = _os.path.join(_os.getcwd(), "logs", "html_dumps")
                                _os.makedirs(dump_dir, exist_ok=True)
                                dump_path = _os.path.join(dump_dir, f"retrofit_diag_{fs_id}.html")
                                try:
                                    with open(dump_path, "w", encoding="utf-8") as df:
                                        df.write(diag_html)
                                    logger.info(f"[Retrofit-Diag] HTML dump salvo: {dump_path}")
                                    html_dumps_saved += 1
                                except Exception as dump_err:
                                    logger.warning(f"[Retrofit-Diag] Falha ao salvar HTML dump: {dump_err}")

                            # Verificar se gravou opening odds no banco (is_opening = TRUE)
                            has_opening = await conn.fetchval("""
                                SELECT EXISTS (
                                    SELECT 1 FROM odds_history
                                    WHERE match_id = $1 AND is_opening = TRUE
                                )
                            """, m_uuid)

                        # ── Determinar status ──────────────────────────────────────────────
                        # 'success'    → opening gravada no banco
                        # 'no_opening' → odds parseadas (linhas de bookmaker extraídas) 
                        #                mas sem dado de abertura → DEFINITIVO
                        # 'failed'     → parser retornou 0 entries OU tabela não carregou
                        #                → RETENTÁVEL (volta à fila na próxima run)
                        has_parsed_odds = len(markets_ok) > 0  # parser extraiu ao menos 1 mercado com entries

                        if has_opening:
                            status = 'success'
                            consecutive_empty = 0  # Reset do circuit breaker
                        elif has_parsed_odds and inserted_count > 0:
                            # Parser extraiu odds E inseriu no banco, mas nenhuma foi opening
                            status = 'no_opening'
                            consecutive_empty = 0  # Reset — o scraping está funcionando
                        elif has_parsed_odds:
                            # Parser extraiu odds mas nenhuma foi inserida (dedup total)
                            # Opening pode já ter sido inserida numa run anterior
                            status = 'no_opening'
                            consecutive_empty = 0
                        else:
                            # Parser retornou 0 entries para TODOS os mercados
                            # → provável mudança de DOM, NÃO queimar a partida
                            status = 'failed'
                            consecutive_empty += 1
                            logger.warning(
                                f"[Retrofit-Diag] {fs_id}: parser retornou 0 entries — "
                                f"marcando como 'failed' (retentável). "
                                f"Consecutive empty: {consecutive_empty}/{CIRCUIT_BREAKER_THRESHOLD}"
                            )
                            
                            # ── Circuit breaker: abortar se muitas falhas consecutivas ──
                            if consecutive_empty >= CIRCUIT_BREAKER_THRESHOLD:
                                circuit_broken = True
                                logger.error(
                                    f"[Retrofit] CIRCUIT BREAKER ATIVADO após {consecutive_empty} "
                                    f"partidas consecutivas sem odds extraídas. "
                                    f"Provável mudança de DOM no Flashscore. Abortando."
                                )
                                # NÃO break aqui — deixa o status da partida atual ser registrado abaixo

                        # Atualiza estatísticas e log da partida em conexão dedicada
                        async with pool.acquire() as conn:
                            if status == 'success':
                                success_matches += 1
                            elif status == 'no_opening':
                                no_opening_matches += 1
                            else:
                                failed_matches += 1
                                
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
                    
                    # Circuit breaker: sair do inner loop após registrar a partida
                    if circuit_broken:
                        break
            
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
        elif circuit_broken:
            # Circuit breaker ativado — marcar liga como 'failed' (retentável)
            # para não queimar mais partidas na próxima run
            cb_msg = (
                f"Circuit breaker ativado após {consecutive_empty} partidas "
                f"consecutivas sem odds extraídas. Provável mudança de DOM."
            )
            await conn.execute("""
                UPDATE retrofit_queue
                SET status = 'failed',
                    error_details = $2
                WHERE league_id = $1
            """, league_id, cb_msg)
            logger.error(f"[Retrofit] Liga {league_id} marcada como 'failed' pelo circuit breaker.")
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
