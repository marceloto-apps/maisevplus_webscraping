import asyncio
import time
import functools
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from apscheduler.triggers.date import DateTrigger

from src.db.pool import get_pool
from src.db.logger import get_logger
from src.alerts.telegram_mini import TelegramAlert
from src.scheduler.key_manager import KeyManager, NoKeysAvailableError
from src.normalizer.team_resolver import TeamResolver
from src.collectors.api_football.api_collector import ApiFootballCollector
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector

logger = get_logger(__name__)

_scheduler_ref = None

# Jobs que devem enviar notificação Telegram quando concluírem com sucesso.
# Jobs de gameday (odds_single_match, lineups_single_match) são excluídos
# para não poluir o chat com dezenas de mensagens por dia.
NOTIFY_ON_SUCCESS: set[str] = {
    "flashscore_historical_backfill",
    "apifootball_backfill",
    "footystats_daily",
    "football_data_daily",
    "fixtures_weekly",
    "flashscore_discovery",
    "db_backup",
    "run_data_quality_routine",
    "flashscore_retrofit_daily",
}

def update_backfill_status(status: str, last_run_started: str = None, last_run_finished: str = None, last_error: str = None, processed_matches: int = None, details: str = None):
    import json
    import os
    status_file = os.path.join(os.getcwd(), "logs", "backfill_status.json")
    os.makedirs(os.path.dirname(status_file), exist_ok=True)
    
    data = {}
    if os.path.exists(status_file):
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
            
    data["status"] = status
    if status in ("running", "success"):
        data["error_notified"] = False
        data["interrupted_notified"] = False
        
    if last_run_started is not None:
        data["last_run_started"] = last_run_started
    if last_run_finished is not None:
        data["last_run_finished"] = last_run_finished
    if last_error is not None:
        data["last_error"] = last_error
    else:
        if status == "success":
            data["last_error"] = None
    if processed_matches is not None:
        data["processed_matches"] = processed_matches
    if details is not None:
        data["details"] = details
        
    try:
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("failed_to_write_backfill_status", error=str(e))

def set_scheduler(scheduler):
    global _scheduler_ref
    _scheduler_ref = scheduler

def safe_job(func):
    """
    Decorator que envolve a rotina do job no wrapper de segurança para
    garantir que exceções não derrubem o trigger do APScheduler
    nem vazem silenciosamente. Adiciona log de telemetria base.
    """
    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
        job_name = func.__name__
        start_time = time.monotonic()
        logger.info("job_started", job_name=job_name)
        _notified = False  # Flag para garantir que alguma notificação foi tentada

        try:
            # A execução da lógica da task
            result = await func(*args, **kwargs)
            
            duration = time.monotonic() - start_time
            duration_min = round(duration / 60, 1)

            # Extrai contagem de registros do resultado de forma inteligente:
            # Prioriza chaves semânticas do dict antes de usar len()
            records_count = None
            if isinstance(result, dict):
                for key in ("records_count", "total", "records_collected", "matches_upserted"):
                    if key in result and result[key] is not None:
                        records_count = result[key]
                        break
            elif isinstance(result, list):
                records_count = len(result)
            elif hasattr(result, "records_collected"):
                records_count = result.records_collected

            logger.info(
                "job_success", 
                job_name=job_name, 
                duration_s=round(duration, 2), 
                records_count=records_count
            )

            # Notificação Telegram de sucesso (apenas para jobs que precisam de visibilidade)
            if job_name in NOTIFY_ON_SUCCESS:
                safe_name = job_name.replace('_', r'\_')
                count_line = f"Registros: {records_count}\n" if records_count is not None else ""
                
                details_text = ""
                if isinstance(result, dict) and result.get("details"):
                    safe_details = result['details'].replace('_', r'\_')
                    details_text = f"\n{safe_details}\n"
                    
                TelegramAlert.fire(
                    "success", 
                    f"*{safe_name}*\n"
                    f"Duração: {duration_min} min\n"
                    f"{count_line}"
                    f"{details_text}"
                )
                _notified = True

        except asyncio.CancelledError:
            logger.info("job_cancelled", job_name=job_name)
            _notified = True  # Não precisa notificar cancelamento
            raise  # Propaga para o orchestrator encerrar
        except NoKeysAvailableError as e:
            logger.warning("job_skipped_no_keys", job_name=job_name, error=str(e))
            safe_name = job_name.replace('_', r'\_')
            TelegramAlert.fire("critical", f"\U0001f511 *{safe_name}*\nTodas as API keys esgotadas.\n{e}")
            _notified = True
        except Exception as e:
            logger.exception("job_failed_unhandled", job_name=job_name, error=str(e))
            try:
                safe_name = job_name.replace('_', r'\_')
                err_text = f"{type(e).__name__}: {str(e)[:300]}"
                TelegramAlert.fire("error", f"\U0001f4a5 *{safe_name}*\nFalha nao tratada.\n{err_text}")
                _notified = True
            except Exception:
                # Se até o fire falhar, o finally fallback cuidará
                logger.error("telegram_fire_in_except_failed", job_name=job_name)
        finally:
            # Tenta disparar o flush após a finalização (ou falha)
            try:
                await TeamResolver.flush_unknowns()
            except Exception as flush_err:
                logger.error("flush_unknowns_failed", error=str(flush_err))
            
            # Fallback: se nenhuma notificação foi enviada para um job que deveria
            # notificar, envia uma notificação genérica de segurança
            if not _notified and job_name in NOTIFY_ON_SUCCESS:
                duration = time.monotonic() - start_time
                duration_min = round(duration / 60, 1)
                try:
                    TelegramAlert.fire(
                        "warning",
                        f"[FALLBACK] Job {job_name} finalizou em {duration_min} min "
                        f"sem notificacao de sucesso ou erro. Verifique os logs."
                    )
                except Exception:
                    pass  # Desistir silenciosamente — o log já foi gravado
    
    return wrapped

# ====================================================================
# FLASHSCORE JOBS
# ====================================================================

@safe_job
async def flashscore_discovery():
    """
    Trigger: 06:00 BRT
    Descobre os Flashscore IDs (jogos passados e futures).
    Roda como subprocess sob xvfb-run para ter display virtual (Camoufox headed).
    """
    import subprocess
    import sys

    try:
        logger.info("spawning_flashscore_discovery_subprocess")
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/run_flashscore_discovery_all.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()

        if proc.returncode != 0:
            stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace")[-600:]
            logger.error("flashscore_discovery_subprocess_failed", returncode=proc.returncode)
            raise RuntimeError(
                f"Subprocess encerrou com código {proc.returncode}.\n{stderr_text}"
            )

        logger.info("flashscore_discovery_subprocess_success")

        # Extrai "Matches atualizados: N" do stdout para o safe_job wrapper
        stdout_text = (stdout_bytes or b"").decode("utf-8", errors="replace")
        import re as _re
        m = _re.search(r"Matches atualizados:\s*(\d+)", stdout_text)
        records_count = int(m.group(1)) if m else None

    except RuntimeError:
        raise
    except Exception as e:
        logger.error("flashscore_discovery_spawn_failed", error=str(e))
        raise

    return {"job": "flashscore_discovery", "records_count": records_count}

@safe_job
async def flashscore_discovery_fixtures():
    """
    Trigger: 05:30 BRT
    Descobre os Flashscore IDs de partidas agendadas (fixtures).
    """
    import subprocess
    import sys

    try:
        logger.info("spawning_flashscore_discovery_fixtures_subprocess")
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/run_flashscore_discovery_fixtures.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()

        if proc.returncode != 0:
            stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace")[-600:]
            logger.error("flashscore_discovery_fixtures_subprocess_failed", returncode=proc.returncode)
            raise RuntimeError(
                f"Subprocess encerrou com código {proc.returncode}.\n{stderr_text}"
            )

        logger.info("flashscore_discovery_fixtures_subprocess_success")

    except RuntimeError:
        raise
    except Exception as e:
        logger.error("flashscore_discovery_fixtures_spawn_failed", error=str(e))
        raise

    return {"job": "flashscore_discovery_fixtures"}

@safe_job
async def flashscore_scheduled_cleaner():
    """
    Trigger: 05:00 BRT
    Limpa e atualiza partidas que ficaram presas no status 'scheduled' no passado.
    """
    import subprocess
    import sys

    try:
        logger.info("spawning_flashscore_scheduled_cleaner_subprocess")
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/run_flashscore_scheduled_cleaner.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()

        if proc.returncode != 0:
            stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace")[-600:]
            logger.error("flashscore_scheduled_cleaner_subprocess_failed", returncode=proc.returncode)
            raise RuntimeError(
                f"Subprocess encerrou com código {proc.returncode}.\n{stderr_text}"
            )

        logger.info("flashscore_scheduled_cleaner_subprocess_success")

    except RuntimeError:
        raise
    except Exception as e:
        logger.error("flashscore_scheduled_cleaner_spawn_failed", error=str(e))
        raise

    return {"job": "flashscore_scheduled_cleaner"}

@safe_job
async def flashscore_integrity_check():
    """
    Trigger: 03:00 BRT
    Verifica a integridade das classes HTML/DOM do Flashscore.
    """
    import subprocess
    import sys

    try:
        logger.info("spawning_flashscore_integrity_check_subprocess")
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/check_flashscore_integrity.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()

        if proc.returncode != 0:
            stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace")[-600:]
            logger.error("flashscore_integrity_check_subprocess_failed", returncode=proc.returncode)
            raise RuntimeError(
                f"Subprocess encerrou com código {proc.returncode}.\n{stderr_text}"
            )

        logger.info("flashscore_integrity_check_subprocess_success")

    except RuntimeError:
        raise
    except Exception as e:
        logger.error("flashscore_integrity_check_spawn_failed", error=str(e))
        raise

    return {"job": "flashscore_integrity_check"}

async def _run_prematch_tracker(phase: str, timeout_hours: float = 2.58):
    import subprocess
    import sys

    GUARD_SECONDS = int(timeout_hours * 3600) + 300  # +5 min de margem

    try:
        logger.info(f"spawning_prematch_tracker_subprocess_phase_{phase}_timeout_{timeout_hours}")
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/run_flashscore_prematch.py", "--phase", phase,
            "--timeout-hours", str(timeout_hours),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=GUARD_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.error(f"prematch_tracker_timeout_phase_{phase}", guard_s=GUARD_SECONDS)
            raise RuntimeError(f"Subprocess encerrou por timeout de {GUARD_SECONDS}s.")

        if proc.returncode != 0:
            stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace")[-600:]
            logger.error(f"prematch_tracker_subprocess_failed_phase_{phase}", returncode=proc.returncode)
            raise RuntimeError(
                f"Subprocess encerrou com código {proc.returncode}.\n{stderr_text}"
            )

        logger.info(f"prematch_tracker_subprocess_success_phase_{phase}")

    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"prematch_tracker_spawn_failed_phase_{phase}", error=str(e))
        raise

    return {"job": f"prematch_tracker_{phase}"}

@safe_job
async def prematch_tracking_1():
    return await _run_prematch_tracker("tracking_2x", timeout_hours=1.83) # 1h50m

@safe_job
async def prematch_tracking_2():
    return await _run_prematch_tracker("tracking_2x", timeout_hours=1.83) # 1h50m

@safe_job
async def prematch_tracking_3():
    return await _run_prematch_tracker("tracking_2x", timeout_hours=2.5) # 2h30m

@safe_job
async def flashscore_complementary(max_matches: int = 150, timeout_hours: float = 2.5):
    """
    Objetivo: Rescrape complementar de faltantes.
    """
    import subprocess
    import sys

    try:
        logger.info("spawning_flashscore_complementary_subprocess", max_matches=max_matches, timeout_hours=timeout_hours)
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/run_flashscore_complementary.py",
            "--limit", str(max_matches),
            "--timeout-hours", str(timeout_hours),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()

        if proc.returncode != 0:
            stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace")[-600:]
            logger.error("flashscore_complementary_subprocess_failed", returncode=proc.returncode)
            raise RuntimeError(
                f"Subprocess encerrou com código {proc.returncode}.\n{stderr_text}"
            )

        logger.info("flashscore_complementary_subprocess_success")
        
        # Extrai os dados se possível
        stdout_text = (stdout_bytes or b"").decode("utf-8", errors="replace")
        import re as _re
        m = _re.search(r"Processadas:\s+(\d+)", stdout_text)
        records_count = int(m.group(1)) if m else None

    except RuntimeError:
        raise
    except Exception as e:
        logger.error("flashscore_complementary_spawn_failed", error=str(e))
        raise

    return {"job": "flashscore_complementary", "records_count": records_count}

@safe_job
async def feed_complementary_queue():
    """Detecta jogos com 1x2 mas sem OU e coloca na fila complementary."""
    from src.db.pool import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute("""
            INSERT INTO fc_complementary_queue (match_id, flashscore_id, kickoff, status, attempts)
            SELECT 
                m.match_id,
                m.flashscore_id,
                m.kickoff,
                'pending',
                0
            FROM matches m
            WHERE m.status = 'finished'
              AND m.flashscore_id IS NOT NULL
              AND m.kickoff < NOW() - INTERVAL '24 hours'
              AND m.kickoff >= NOW() - INTERVAL '90 days'
              AND EXISTS (
                  SELECT 1 FROM odds_history oh 
                  WHERE oh.match_id = m.match_id 
                    AND oh.time >= m.kickoff - INTERVAL '14 days'
                    AND oh.time <= m.kickoff + INTERVAL '2 days'
                    AND oh.source = 'flashscore' 
                    AND oh.market_type = '1x2' AND oh.period = 'ft'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM odds_history oh 
                  WHERE oh.match_id = m.match_id 
                    AND oh.time >= m.kickoff - INTERVAL '14 days'
                    AND oh.time <= m.kickoff + INTERVAL '2 days'
                    AND oh.source = 'flashscore' 
                    AND oh.market_type = 'ou' AND oh.period = 'ft'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM fc_complementary_queue fcq 
                  WHERE fcq.match_id = m.match_id 
                    AND fcq.status = 'completed'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM fc_complementary_queue fcq 
                  WHERE fcq.match_id = m.match_id 
                    AND fcq.attempts >= 3
              )
            ON CONFLICT (match_id) DO NOTHING
        """)
        inserted = 0
        if res.startswith("INSERT"):
            try:
                inserted = int(res.split(" ")[-1])
            except Exception:
                pass
        logger.info("feed_complementary_queue_success", inserted=inserted)
        return {"job": "feed_complementary_queue", "inserted": inserted}

@safe_job
async def flashscore_dynamic_prematch(match_id: str, phase: str):
    import subprocess
    import sys

    try:
        logger.info(f"spawning_flashscore_dynamic_prematch_phase_{phase}_match_{match_id}")
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/run_flashscore_prematch.py", 
            "--phase", phase, "--match_id", match_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()

        if proc.returncode != 0:
            stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace")[-600:]
            logger.error(f"flashscore_dynamic_prematch_failed_phase_{phase}", returncode=proc.returncode)
            raise RuntimeError(
                f"Subprocess encerrou com código {proc.returncode}.\n{stderr_text}"
            )

    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"flashscore_dynamic_prematch_spawn_failed_phase_{phase}", error=str(e))
        raise

    return {"job": f"fs_dynamic_{phase}", "match_id": match_id}



@safe_job
async def flashscore_odds_standard():
    """
    Trigger: 07:00, 11:00, 15:00, 21:00 BRT
    Busca odds completas via Flashscore para jogos da próxima semana.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT match_id, flashscore_id 
            FROM matches 
            WHERE kickoff > now() AND kickoff < now() + interval '7 days'
            AND flashscore_id IS NOT NULL
        ''')
        
    match_ids = [{"match_id": r['match_id'], "flashscore_id": r['flashscore_id']} for r in rows]
    
    if match_ids:
        collector = FlashscoreOddsCollector()
        res = await collector.collect(match_ids=match_ids)
        return {"total_collected": res.records_collected, "new": res.records_new}
    return {"total_collected": 0, "new": 0}

    
@safe_job
async def flashscore_closing_odds():
    """
    Trigger: 01:00 BRT
    Busca closing odds de todos os jogos que finalizaram ontem.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT match_id, flashscore_id 
            FROM matches 
            WHERE kickoff >= current_date - interval '1 day' 
              AND kickoff < current_date
            AND flashscore_id IS NOT NULL
        ''')
        
    match_ids = [{"match_id": r['match_id'], "flashscore_id": r['flashscore_id']} for r in rows]
    
    if match_ids:
        collector = FlashscoreOddsCollector()
        res = await collector.collect(match_ids=match_ids, is_closing=True)
        
        # Após a coleta das closing odds originais da partida terminar, 
        # marcamos o último snapshot do tracker como closing_prematch
        pool = await get_pool()
        async with pool.acquire() as conn:
            for m in match_ids:
                try:
                    await conn.execute("SELECT mark_closing_prematch($1)", m["match_id"])
                except Exception as e:
                    logger.error(f"Erro ao chamar mark_closing_prematch para {m['match_id']}: {e}")
                    
        return {"total_closing": res.records_collected, "new": res.records_new}
    return {"total_closing": 0, "new": 0}


@safe_job
async def reset_daily_keys():
    """
    Trigger: `0 0 * * *` UTC
    Objetivo: Reseta Budget Usage
    """
    await KeyManager.reset_daily()
    logger.info("job_executing_key_reset")

@safe_job
async def reset_monthly_keys():
    """
    Trigger: `0 0 1 * *` UTC
    Objetivo: Reseta Budget Mensal
    """
    await KeyManager.reset_monthly()
    logger.info("job_executing_monthly_key_reset")

@safe_job
async def schedule_gameday_jobs():
    """
    Trigger: `30 0 * * *` 
    Objetivo: Descobrir jogos de hoje (via v_today_matches) e alocar triggers pontuais.
    """
    if not _scheduler_ref:
        raise Exception("Scheduler reference is missing! Orchestrator must call set_scheduler.")

    pool = await get_pool()
    queries = []
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM v_today_matches")
        
    jobs_created = 0
    now_sp = datetime.now(ZoneInfo("America/Sao_Paulo"))

    for match in rows:
        kickoff = match["kickoff"]  # TIMESTAMPTZ, converte bem para comparison timezone-aware
        match_id_uuid = str(match["match_id"])
        
        # Array de Triggers que faremos para o Jogo:
        # T-60 (Lineups & Odds Inicial), T-30 (Odds Finais 1), T-5 (Closing)
        placements = [
            # Desativados devido ao limite rígido de 100 requests diários da API-Football
            # (-60, "pre60_lineups", lineups_single_match),
            # Flashscore Tracking Dinâmicos reducao temporaria: pre30 removido, preservando pre2
            (-2, "pre2", flashscore_dynamic_prematch),
        ]

        for offset_min, label, job_func in placements:
            trigger_time = kickoff + timedelta(minutes=offset_min)
            
            # Pula se o tempo do offset já expirou
            if trigger_time <= now_sp:
                continue
                
            job_id = f"gameday_{match_id_uuid}_{label}"
            
            if _scheduler_ref.get_job(job_id):
                continue
                
            kwargs = {"match_id": match_id_uuid}
            if job_func == flashscore_dynamic_prematch:
                kwargs["phase"] = label
                
            _scheduler_ref.add_job(
                job_func,
                DateTrigger(run_date=trigger_time),
                kwargs=kwargs,
                id=job_id,
                misfire_grace_time=300,
                replace_existing=True
            )
            jobs_created += 1

    return {"jobs_created": jobs_created, "matches_today": len(rows)}

# Mocks para imports mantidos do orchestator
@safe_job
async def footystats_daily():
    """
    Trigger: `0 5 * * *` BRT
    Objetivo: Atualizar todos os jogos das temporadas ativas via FootyStats API.
    Ao final avalia encerramento automático de temporadas concluídas.
    """
    from src.collectors.footystats.daily_updater import FootyStatsDailyUpdater
    updater = FootyStatsDailyUpdater()
    result = await updater.run()
    logger.info(
        "footystats_daily_complete",
        seasons_processed=result.get("seasons_processed"),
        matches_upserted=result.get("matches_upserted"),
        seasons_closed=result.get("seasons_closed"),
    )
    return result


@safe_job
async def football_data_daily():
    """
    Trigger: `15 5 * * *` BRT
    Objetivo: Atualizar CSVs da football-data.co.uk para temporadas ativas.
    Ligas sem football_data_code são silenciosamente ignoradas.
    """
    from src.collectors.football_data.csv_collector import FootballDataCollector
    collector = FootballDataCollector()
    result = await collector.collect(mode="daily-update")
    return {"provider": "football_data", "mode": "daily-update", "total": result.records_collected}


@safe_job
async def apifootball_backfill():
    """
    Trigger: `0 4 * * *` BRT (04:15 após ajuste)
    Objetivo: Backfill reversivo das temporadas atuais (a partir de 03/04).
    Lê estado local e consome até 100 requisições diárias (limite da conta grátis).
    Desconecta a NordVPN antes de rodar para garantir IP real na API-Football.
    """
    import subprocess

    # Garante que a VPN está desconectada (API-Football bloqueia IPs de VPN)
    try:
        logger.info("nordvpn_disconnecting_for_apifootball")
        subprocess.run(["nordvpn", "disconnect"], check=True, capture_output=True, text=True, timeout=30)
        logger.info("nordvpn_disconnected_ok")
    except FileNotFoundError:
        logger.warning("nordvpn_binary_not_found_skipping_disconnect")
    except subprocess.CalledProcessError as e:
        logger.warning("nordvpn_disconnect_failed", error=e.stderr.strip())
    except subprocess.TimeoutExpired:
        logger.warning("nordvpn_disconnect_timeout")

    from scripts.run_apifootball_backfill import run_backfill
    result = await run_backfill(is_cron=True)
    # run_backfill pode retornar dict com stats ou None
    records_count = None
    if isinstance(result, dict):
        records_count = result.get("total_processed") or result.get("records_collected")
    return {"provider": "api_football", "job": "backfill_daily", "records_count": records_count}

@safe_job
async def flashscore_historical_backfill():
    """
    Trigger: `0 6,10,14,18 * * *` BRT
    Objetivo: Rodízio de IP (NordVPN) e backfill em lote do Flashscore.
    """
    update_backfill_status(
        "running",
        last_run_started=datetime.now(timezone.utc).isoformat()
    )
    import subprocess
    import sys
    import random
    import re
    details = None
    
    # Servidores homologados para rodízio (6 servidores)
    servers = ["br89", "br105", "br75", "br116", "br76", "br81"]
    target_server = random.choice(servers)
    
    # 1. Tentar rotacionar o IP via NordVPN
    try:
        logger.info("nordvpn_connecting", server=target_server)
        res = subprocess.run(["nordvpn", "connect", target_server], check=True, capture_output=True, text=True, timeout=45)
        
        # Puxa o status real para inspecionar o IP
        status_res = subprocess.run(["nordvpn", "status"], capture_output=True, text=True, timeout=20)
        ip_match = re.search(r"\bIP:\s*([\d\.]+)", status_res.stdout)
        new_ip = ip_match.group(1) if ip_match else "Desconhecido"
        
        logger.info("nordvpn_reconnected", server=target_server, ip=new_ip)
        
    except FileNotFoundError:
        logger.warning("nordvpn_binary_not_found_skipping_rotation")
    except subprocess.CalledProcessError as e:
        logger.error("nordvpn_failed", error=e.stderr.strip())
    except subprocess.TimeoutExpired as e:
        logger.error("nordvpn_timeout", cmd=str(e.cmd), timeout=e.timeout)

    # Janela de tempo por execução (horas). O filho para sozinho nesse limite;
    # o pai tem um guard de +5 min para não bloquear o orchestrator para sempre.
    WINDOW_HOURS = 2.58  # ~2h35m
    GUARD_SECONDS = int(WINDOW_HOURS * 3600) + 300  # +5 min de margem

    # 2. Spawn subprocess para limpar memória após a execução (o browser come muito)
    try:
        logger.info("spawning_flashscore_backfill_subprocess", timeout_hours=WINDOW_HOURS)
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/run_sequential_backfill.py",
            "--timeout-hours", str(WINDOW_HOURS),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=GUARD_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.error("flashscore_backfill_subprocess_timeout", guard_s=GUARD_SECONDS)
            raise RuntimeError(
                f"Subprocess não encerrou em {GUARD_SECONDS}s — processo morto forçadamente."
            )

        if proc.returncode != 0:
            stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace")[-600:]
            logger.error("flashscore_backfill_subprocess_failed", returncode=proc.returncode)
            raise RuntimeError(
                f"Subprocess encerrou com código {proc.returncode}.\n{stderr_text}"
            )

        logger.info("flashscore_backfill_subprocess_success")

        # Tenta extrair `Completados com sucesso` do stdout para o Telegram
        stdout_text = (stdout_bytes or b"").decode("utf-8", errors="replace")
        import re as _re
        m = _re.search(r"Completados com sucesso:\s+(\d+)", stdout_text)
        records_count = int(m.group(1)) if m else None

        # Tenta extrair o resumo detalhado do stdout
        if "=== RESUMO DE EXECUCAO ===" in stdout_text:
            parts = stdout_text.split("=== RESUMO DE EXECUCAO ===")
            if len(parts) > 1:
                summary_part = parts[1].strip().split("\n")
                summary_lines = []
                for line in summary_part:
                    if line.strip().startswith("- "):
                        summary_lines.append(line.strip())
                if summary_lines:
                    details = "\n".join(summary_lines)

        update_backfill_status(
            "success",
            last_run_finished=datetime.now(timezone.utc).isoformat(),
            processed_matches=records_count,
            details=details
        )

    except RuntimeError as e:
        update_backfill_status(
            "error",
            last_run_finished=datetime.now(timezone.utc).isoformat(),
            last_error=str(e)
        )
        raise  # Re-propagado para o safe_job capturar e notificar Telegram
    except Exception as e:
        update_backfill_status(
            "error",
            last_run_finished=datetime.now(timezone.utc).isoformat(),
            last_error=f"{type(e).__name__}: {str(e)}"
        )
        logger.error("flashscore_backfill_spawn_failed", error=str(e))
        raise
    finally:
        # Garante desconexão da NordVPN ao final do processo
        try:
            logger.info("nordvpn_disconnecting_after_backfill")
            subprocess.run(["nordvpn", "disconnect"], check=True, capture_output=True, text=True, timeout=30)
            logger.info("nordvpn_disconnected_ok")
        except FileNotFoundError:
            pass  # Caso não tenha NordVPN instalado localmente (ex: Windows em dev)
        except Exception as e:
            logger.warning("nordvpn_disconnect_failed", error=str(e))

    return {"job": "flashscore_historical_backfill", "records_count": records_count, "details": details}


@safe_job
async def flashscore_retrofit_daily():
    """
    Trigger: 01:15 BRT
    Retrofit diário de opening odds usando a tabela retrofit_queue como controle de fila.
    """
    import subprocess
    import sys
    import random
    import re

    # 1. Tentar conectar ao Brasil via NordVPN para carregar bookmakers brasileiros (ex: bet365/Betano)
    servers = ["br89", "br105", "br75", "br116", "br76", "br81"]
    target_server = random.choice(servers)
    
    try:
        logger.info("nordvpn_connecting_for_retrofit", server=target_server)
        subprocess.run(["nordvpn", "connect", target_server], check=True, capture_output=True, text=True, timeout=45)
        
        status_res = subprocess.run(["nordvpn", "status"], capture_output=True, text=True, timeout=20)
        ip_match = re.search(r"\bIP:\s*([\d\.]+)", status_res.stdout)
        new_ip = ip_match.group(1) if ip_match else "Desconhecido"
        logger.info("nordvpn_connected_for_retrofit_ok", server=target_server, ip=new_ip)
    except FileNotFoundError:
        logger.warning("nordvpn_binary_not_found_skipping_rotation_for_retrofit")
    except subprocess.CalledProcessError as e:
        logger.error("nordvpn_failed_for_retrofit", error=e.stderr.strip())
    except subprocess.TimeoutExpired as e:
        logger.error("nordvpn_timeout_for_retrofit", cmd=str(e.cmd), timeout=e.timeout)

    # Janela de tempo de segurança (3 horas de limite)
    GUARD_SECONDS = 3 * 3600 + 300

    try:
        logger.info("spawning_flashscore_retrofit_subprocess")
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/run_flashscore_retrofit.py",
            "--limit-matches", "400", "--headless",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=GUARD_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.error("flashscore_retrofit_subprocess_timeout", guard_s=GUARD_SECONDS)
            raise RuntimeError(
                f"Subprocess do retrofit não encerrou em {GUARD_SECONDS}s — processo morto forçadamente."
            )

        if proc.returncode != 0:
            stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace")[-600:]
            logger.error("flashscore_retrofit_subprocess_failed", returncode=proc.returncode)
            raise RuntimeError(
                f"Subprocess do retrofit encerrou com código {proc.returncode}.\n{stderr_text}"
            )

        logger.info("flashscore_retrofit_subprocess_success")

        # Extrai estatísticas do stdout para o safe_job / Telegram
        stdout_text = (stdout_bytes or b"").decode("utf-8", errors="replace")
        import re as _re
        
        success_matches = 0
        matches = _re.findall(r"Sucesso \(gravou opening\):\s*(\d+)", stdout_text)
        if matches:
            success_matches = sum(int(m) for m in matches)
            
        no_opening = 0
        matches_no = _re.findall(r"Sem opening no Flashscore \(no_opening\):\s*(\d+)", stdout_text)
        if matches_no:
            no_opening = sum(int(m) for m in matches_no)

        details = f"Sucesso (opening gravada): {success_matches}\nSem opening: {no_opening}"

    except RuntimeError:
        raise
    except Exception as e:
        logger.error("flashscore_retrofit_spawn_failed", error=str(e))
        raise
    finally:
        # Garante desconexão da NordVPN ao final do processo
        try:
            logger.info("nordvpn_disconnecting_after_retrofit")
            subprocess.run(["nordvpn", "disconnect"], check=True, capture_output=True, text=True, timeout=30)
            logger.info("nordvpn_disconnected_after_retrofit_ok")
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning("nordvpn_disconnect_after_retrofit_failed", error=str(e))

    return {"job": "flashscore_retrofit_daily", "records_count": success_matches, "details": details}


@safe_job
async def db_backup():
    """
    Trigger: `20 4 * * *` BRT (diário às 04:20)
    Objetivo: Backup comprimido do PostgreSQL enviado ao OneDrive via rclone.
    Mantém os 5 últimos backups no OneDrive e 2 dias localmente.
    """
    import re as _re

    # Timeout generoso: pg_dump + upload podem demorar em bases grandes
    BACKUP_TIMEOUT_S = 600  # 10 minutos

    try:
        logger.info("db_backup_starting")
        proc = await asyncio.create_subprocess_exec(
            "/bin/bash", "scripts/backup_db.sh",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=BACKUP_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.error("db_backup_timeout", timeout_s=BACKUP_TIMEOUT_S)
            raise RuntimeError(f"Backup excedeu o timeout de {BACKUP_TIMEOUT_S}s — processo encerrado.")

        stdout_text = (stdout_bytes or b"").decode("utf-8", errors="replace")
        stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace")

        if proc.returncode != 0:
            logger.error("db_backup_failed", returncode=proc.returncode, stderr=stderr_text[-400:])
            raise RuntimeError(f"backup_db.sh encerrou com código {proc.returncode}.\n{stderr_text[-400:]}")

        # Extrai tamanho do backup do stdout (ex: "SIZE: 42M")
        m = _re.search(r"SIZE:\s*([\d\.]+\s*\w+)", stdout_text)
        backup_size = m.group(1) if m else "?"

        logger.info("db_backup_success", size=backup_size)

    except RuntimeError:
        raise
    except Exception as e:
        logger.error("db_backup_spawn_failed", error=str(e))
        raise

    return {"job": "db_backup", "records_count": backup_size}

# ---------------------------------------------------------------------------
@safe_job
async def odds_prematch_30(): pass

@safe_job
async def odds_prematch_2(): pass

@safe_job
async def results_postmatch(): pass

@safe_job
async def xg_postround(): pass

@safe_job
async def lineups_prematch(): pass

@safe_job
async def csv_weekly(): pass

@safe_job
async def health_check():
    """
    Trigger: 03:00 BRT (diário)
    Heartbeat diário — confirma no Telegram que o orchestrator está vivo
    e lista as rotinas que serão disparadas hoje.
    """
    from datetime import date
    now_brt = datetime.now(ZoneInfo("America/Sao_Paulo"))
    today_str = now_brt.strftime("%d/%m/%Y")
    weekday = now_brt.strftime("%A")

    WEEKDAY_PT = {
        "Monday": "Segunda", "Tuesday": "Terça", "Wednesday": "Quarta",
        "Thursday": "Quinta", "Friday": "Sexta", "Saturday": "Sábado", "Sunday": "Domingo"
    }
    weekday_pt = WEEKDAY_PT.get(weekday, weekday)

    is_monday = now_brt.weekday() == 0  # segunda

    schedule_lines = [
        "🗓 Rotinas Fixas de hoje:",
        "  00:20 — Data Quality Routine",
        "  00:30 — Schedule Gameday Dinâmico",
        "  01:15 — Flashscore Retrofit Daily",
        "  03:00 — Flashscore Integrity Check",
        "  03:15 — Heartbeat / Notificações",
        "  03:20 — API-Football Backfill",
        "  03:30 — Flashscore Complementary Daily",
        "  03:30 — FootyStats Daily",
        "  03:40 — Football-Data Daily",
        "  03:50 — 💾 Backup DB → OneDrive",
        "  04:20 — Flashscore Scheduled Cleaner",
        "  05:15 — Flashscore Discovery Fixtures",
        "  06:20 — Flashscore Prematch Tracking 1",
        "  08:20 — Flashscore Backfill (janela 2)",
        "  11:05 — Flashscore Backfill (janela 3)",
        "  13:50 — Flashscore Prematch Tracking 2",
        "  15:50 — Flashscore Backfill (janela 4)",
        "  18:35 — Flashscore Backfill (janela 5)",
        "  21:20 — Flashscore Prematch Tracking 3",
        "  22:30 — Flashscore Backfill (janela 1)",
        "  23:50 — Reset Daily Keys"
    ]

    schedule_txt = "\n".join(schedule_lines)

    TelegramAlert.fire(
        "info",
        f"💓 *Orchestrator Alive*\n"
        f"{weekday_pt}, {today_str} — 03:00 BRT\n\n"
        f"{schedule_txt}"
    )



@safe_job
async def run_data_quality_routine():
    """
    Trigger: 00:20 BRT (diário)
    Avalia a qualidade e cobertura dos dados dos jogos finalizados.
    Gera relatório detalhado em log e relatório resumido no Telegram.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Upsert da qualidade dos dados das partidas finalizadas
        await conn.execute('''
            WITH stats_flags AS (
                SELECT
                    m.match_id,
                    MAX(CASE WHEN ms.shots_home IS NOT NULL THEN 1 ELSE 0 END) AS has_footystats_stats,
                    MAX(CASE WHEN ms.total_passes_home IS NOT NULL OR ms.expected_goals_home IS NOT NULL THEN 1 ELSE 0 END) AS has_apifootball_stats,
                    MAX(CASE WHEN ms_fs.xg_home_ft IS NOT NULL OR ms_fs.xgot_home_ft IS NOT NULL THEN 1 ELSE 0 END) AS has_flashscore_stats
                FROM matches m
                LEFT JOIN match_stats ms ON m.match_id = ms.match_id
                LEFT JOIN match_stats_fs ms_fs ON m.match_id = ms_fs.match_id
                GROUP BY m.match_id
            ),
            odds_flags AS (
                SELECT
                    match_id,
                    MAX(CASE WHEN source = 'football_data' THEN 1 ELSE 0 END) AS has_fd_odds,
                    MAX(CASE WHEN source = 'flashscore' THEN 1 ELSE 0 END) AS has_fs_odds
                FROM odds_history
                GROUP BY match_id
            )
            INSERT INTO match_data_quality (
                match_id, 
                missing_footystats_stats, 
                missing_apifb_stats, 
                missing_flashscore_stats, 
                missing_fd_odds, 
                missing_fs_odds,
                updated_at
            )
            SELECT
                m.match_id,
                COALESCE(sf.has_footystats_stats, 0) = 0,
                COALESCE(sf.has_apifootball_stats, 0) = 0,
                COALESCE(sf.has_flashscore_stats, 0) = 0,
                COALESCE(of_.has_fd_odds, 0) = 0,
                COALESCE(of_.has_fs_odds, 0) = 0,
                NOW()
            FROM matches m
            LEFT JOIN stats_flags sf ON sf.match_id = m.match_id
            LEFT JOIN odds_flags of_ ON of_.match_id = m.match_id
            WHERE m.status = 'finished'
            ON CONFLICT (match_id) DO UPDATE SET
                missing_footystats_stats = EXCLUDED.missing_footystats_stats,
                missing_apifb_stats = EXCLUDED.missing_apifb_stats,
                missing_flashscore_stats = EXCLUDED.missing_flashscore_stats,
                missing_fd_odds = EXCLUDED.missing_fd_odds,
                missing_fs_odds = EXCLUDED.missing_fs_odds,
                updated_at = EXCLUDED.updated_at
        ''')

        # 1.5. Update odds quality flags
        await conn.execute('''
            WITH match_odds_data AS (
                SELECT 
                    match_id, 
                    market_type, 
                    line, 
                    odds_1, 
                    odds_x, 
                    odds_2,
                    LAG(odds_1) OVER (PARTITION BY match_id, market_type ORDER BY line) as prev_odds_1,
                    LAG(odds_2) OVER (PARTITION BY match_id, market_type ORDER BY line) as prev_odds_2,
                    MAX(odds_1) OVER (PARTITION BY match_id, market_type) as max_odds_1,
                    MIN(odds_1) OVER (PARTITION BY match_id, market_type) as min_odds_1,
                    COUNT(*) OVER (PARTITION BY match_id, market_type) as line_count
                FROM odds_history
                WHERE period = 'ft'
            ),
            eval_flags AS (
                SELECT
                    match_id,
                    -- 1x2 flags
                    MAX(CASE WHEN market_type IN ('1x2', 'match_odds') AND (
                        odds_1 <= 1.00 OR odds_1 > 50.0 OR
                        odds_x <= 1.00 OR odds_x > 50.0 OR
                        odds_2 <= 1.00 OR odds_2 > 50.0 OR
                        odds_1 = odds_x OR odds_1 = odds_2 OR odds_x = odds_2 OR
                        odds_1 IS NULL OR odds_x IS NULL OR odds_2 IS NULL OR
                        ((1.0/NULLIF(odds_1,0)) + (1.0/NULLIF(odds_x,0)) + (1.0/NULLIF(odds_2,0))) < 1.02 OR
                        ((1.0/NULLIF(odds_1,0)) + (1.0/NULLIF(odds_x,0)) + (1.0/NULLIF(odds_2,0))) > 1.20
                    ) THEN 1 ELSE 0 END) AS suspicious_1x2_odds,
                    
                    -- OU flags (over_odds = odds_1, under_odds = odds_2)
                    MAX(CASE WHEN market_type IN ('ou', 'over_under') AND (
                        odds_1 <= 1.00 OR odds_1 > 30.0 OR
                        odds_2 <= 1.00 OR odds_2 > 30.0 OR
                        odds_1 IS NULL OR odds_2 IS NULL OR
                        odds_1 = odds_2 OR
                        (line_count > 1 AND max_odds_1 = min_odds_1) OR
                        (prev_odds_1 IS NOT NULL AND odds_1 <= prev_odds_1) OR
                        (prev_odds_2 IS NOT NULL AND odds_2 >= prev_odds_2) 
                    ) THEN 1 ELSE 0 END) AS suspicious_ou_odds,
                    
                    -- AH flags
                    MAX(CASE WHEN market_type IN ('ah', 'asian_handicap') AND (
                        odds_1 <= 1.00 OR odds_1 > 20.0 OR
                        odds_2 <= 1.00 OR odds_2 > 20.0 OR
                        odds_1 IS NULL OR odds_2 IS NULL OR
                        odds_1 = odds_2 OR
                        (line_count > 1 AND max_odds_1 = min_odds_1) OR
                        (prev_odds_1 IS NOT NULL AND odds_1 >= prev_odds_1) OR
                        (prev_odds_2 IS NOT NULL AND odds_2 <= prev_odds_2)
                    ) THEN 1 ELSE 0 END) AS suspicious_ah_odds
                FROM match_odds_data
                GROUP BY match_id
            )
            UPDATE match_data_quality mdq
            SET 
                suspicious_1x2_odds = (COALESCE(ef.suspicious_1x2_odds, 0) = 1),
                suspicious_ou_odds  = (COALESCE(ef.suspicious_ou_odds, 0) = 1),
                suspicious_ah_odds  = (COALESCE(ef.suspicious_ah_odds, 0) = 1)
            FROM eval_flags ef
            WHERE mdq.match_id = ef.match_id
              AND NOT (mdq.missing_fd_odds = TRUE AND mdq.missing_fs_odds = TRUE);
        ''')

        # 2. Obter totais de cobertura global e odds suspeitas
        totals_row = await conn.fetchrow('''
            SELECT
                COUNT(*) AS total_matches,
                COUNT(*) FILTER (WHERE NOT mq.missing_footystats_stats) AS footystats_stats,
                COUNT(*) FILTER (WHERE NOT mq.missing_apifb_stats) AS apifootball_stats,
                COUNT(*) FILTER (WHERE NOT mq.missing_flashscore_stats) AS flashscore_stats,
                COUNT(*) FILTER (WHERE NOT mq.missing_fd_odds) AS football_data_odds,
                COUNT(*) FILTER (WHERE NOT mq.missing_fs_odds) AS flashscore_odds,
                COUNT(*) FILTER (WHERE mq.suspicious_1x2_odds) AS susp_1x2,
                COUNT(*) FILTER (WHERE mq.suspicious_ou_odds) AS susp_ou,
                COUNT(*) FILTER (WHERE mq.suspicious_ah_odds) AS susp_ah
            FROM matches m
            JOIN match_data_quality mq ON mq.match_id = m.match_id
            WHERE m.status = 'finished'
        ''')
        
        total_matches = totals_row['total_matches'] or 0
        if total_matches == 0:
            return {"status": "no_matches"}
            
        def pct(count):
            return round((count * 100.0) / total_matches, 1)

        from datetime import date
        today_str = date.today().strftime("%d/%m/%Y")
        
        # Valores seguros para formatação (evita None literal)
        fs_st = totals_row['footystats_stats'] or 0
        ap_st = totals_row['apifootball_stats'] or 0
        fl_st = totals_row['flashscore_stats'] or 0
        fd_od = totals_row['football_data_odds'] or 0
        fs_od = totals_row['flashscore_odds'] or 0
        s_1x2 = totals_row['susp_1x2'] or 0
        s_ou  = totals_row['susp_ou'] or 0
        s_ah  = totals_row['susp_ah'] or 0

        tg_msg = [
            f"📊 *Data Quality Report — {today_str}*",
            f"Jogos finalizados analisados: {total_matches}",
            "",
            "✅ *Cobertura Geral:*",
            f"  FootyStats:  {fs_st}/{total_matches} ({pct(fs_st)}%)",
            f"  APIFootball: {ap_st}/{total_matches} ({pct(ap_st)}%)",
            f"  FlashScore:  {fl_st}/{total_matches} ({pct(fl_st)}%)",
            f"  FD Odds:     {fd_od}/{total_matches} ({pct(fd_od)}%)",
            f"  FS Odds:     {fs_od}/{total_matches} ({pct(fs_od)}%)",
            "",
            "🔍 *Auditoria de Odds:*",
            f"  Odds 1x2 suspeitas: {s_1x2}/{total_matches} ({pct(s_1x2)}%)",
            f"  Odds OU suspeitas:  {s_ou}/{total_matches} ({pct(s_ou)}%)",
            f"  Odds AH suspeitas:  {s_ah}/{total_matches} ({pct(s_ah)}%)",
            ""
        ]

        # 3. Obter Top 5 Offenders (Gaps e Odds)
        offenders = await conn.fetch('''
            SELECT 
                l.code AS league_code, 
                s.label AS season, 
                COUNT(*) AS total_issues
            FROM matches m
            JOIN leagues l ON l.league_id = m.league_id
            JOIN seasons s ON s.season_id = m.season_id
            JOIN match_data_quality mq ON mq.match_id = m.match_id
            WHERE m.status = 'finished'
              AND (mq.missing_footystats_stats OR mq.missing_apifb_stats 
                   OR mq.missing_flashscore_stats OR mq.missing_fd_odds OR mq.missing_fs_odds
                   OR mq.suspicious_1x2_odds OR mq.suspicious_ah_odds OR mq.suspicious_ou_odds)
            GROUP BY l.code, s.label
            ORDER BY total_issues DESC
            LIMIT 5
        ''')

        if offenders:
            tg_msg.append("⚠️ *Ligas com mais inconsistências (Top 5):*")
            for row in offenders:
                league_code = (row['league_code'] or '?').replace('_', r'\_')
                tg_msg.append(f"  {league_code} {row['season']}: {row['total_issues']} jogos com falhas")
        else:
            tg_msg.append("🎉 *Todas as ligas estão 100% completas!*")
            
        tg_msg.append("")
        tg_msg.append("🔗 Relatório completo salvo no log.")
        
        # 4. Notificar via telegram (relatório consolidado)
        TelegramAlert.fire("info", "\n".join(tg_msg))
        # Retorna logo após o fire para que o safe_job NÃO envie uma segunda notificação SUCCESS.
        # O records_count é injetado no retorno apenas para telemetria de log.

        
        # 5. Log Detalhado (Breakdown)
        details = await conn.fetch('''
            SELECT 
                l.code AS league_code, 
                s.label AS season, 
                COUNT(*) AS count_matches,
                COUNT(*) FILTER (WHERE NOT mq.missing_footystats_stats) AS count_footystats,
                COUNT(*) FILTER (WHERE NOT mq.missing_apifb_stats) AS count_apifb,
                COUNT(*) FILTER (WHERE NOT mq.missing_flashscore_stats) AS count_fs_stats,
                COUNT(*) FILTER (WHERE NOT mq.missing_fd_odds) AS count_fd_odds,
                COUNT(*) FILTER (WHERE NOT mq.missing_fs_odds) AS count_fs_odds,
                COUNT(*) FILTER (WHERE mq.suspicious_1x2_odds OR mq.suspicious_ah_odds OR mq.suspicious_ou_odds) AS count_suspicious
            FROM matches m
            JOIN leagues l ON l.league_id = m.league_id
            JOIN seasons s ON s.season_id = m.season_id
            JOIN match_data_quality mq ON mq.match_id = m.match_id
            WHERE m.status = 'finished'
            GROUP BY l.code, s.label
            ORDER BY l.code ASC, s.label DESC
        ''')
        
        logger.info("data_quality_detailed_breakdown_start")
        for r in details:
            logger.info("dqr_league", 
                        league=r['league_code'], season=r['season'], 
                        total=r['count_matches'], 
                        fs_st=r['count_footystats'], ap_st=r['count_apifb'], fl_st=r['count_fs_stats'],
                        fd_od=r['count_fd_odds'], fs_od=r['count_fs_odds'], susp_odds=r['count_suspicious'])
        logger.info("data_quality_detailed_breakdown_end")

        return {"records_count": total_matches}


@safe_job
async def check_backfill_status():
    """
    Trigger: a cada hora
    Objetivo: Executar o script de monitoramento do status do backfill.
    """
    import sys
    import asyncio
    logger.info("running_watchdog_status_check")
    # Executa o subprocess check_backfill_status.py
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "scripts/check_backfill_status.py",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    if proc.returncode != 0:
        stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace")[-300:]
        logger.error("watchdog_status_check_failed", returncode=proc.returncode, error=stderr_text)
        raise RuntimeError(f"Watchdog check_backfill_status.py falhou: {stderr_text}")
    logger.info("watchdog_status_check_success")
    return {"job": "check_backfill_status"}

