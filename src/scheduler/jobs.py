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
from src.collectors.odds_api.api_collector import OddsApiCollector
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
}

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
                count_line = f"Registros: `{records_count}`\n" if records_count is not None else ""
                TelegramAlert.fire(
                    "success", 
                    f"*{job_name}*\n"
                    f"Duração: `{duration_min} min`\n"
                    f"{count_line}"
                )

        except asyncio.CancelledError:
            logger.info("job_cancelled", job_name=job_name)
            raise  # Propaga para o orchestrator encerrar
        except NoKeysAvailableError as e:
            logger.warning("job_skipped_no_keys", job_name=job_name, error=str(e))
            TelegramAlert.fire("critical", f"🔑 *{job_name}*\nTodas as API keys esgotadas.\n`{e}`")
        except Exception as e:
            logger.exception("job_failed_unhandled", job_name=job_name, error=str(e))
            TelegramAlert.fire("error", f"💥 *{job_name}*\nFalha não tratada.\n`{type(e).__name__}: {e}`")
        finally:
            # Tenta disparar o flush após a finalização (ou falha)
            try:
                await TeamResolver.flush_unknowns()
            except Exception as flush_err:
                logger.error("flush_unknowns_failed", error=str(flush_err))
    
    return wrapped

# ====================================================================
# DEFINIÇÃO DOS JOBS
# ====================================================================

@safe_job
async def odds_standard():
    """
    Trigger: `0 6,10,14,20 * * *`
    Objetivo: Buscar via OddsAPI os matches (Tier > ampla cobertura).
    """
    collector = OddsApiCollector()
    result = await collector.collect(mode="validation")
    return {"provider": "odds_api", "mode": "validation", "total": result.records_collected}

@safe_job
async def odds_gameday_hourly():
    """
    Trigger: cron '8-23', minute=0
    Objetivo: Buscar as Odds dos Matches D+0 (Hoje) não iniciados via OddsApi (Tiers 1 e 2).
    """
    collector = OddsApiCollector()
    result = await collector.collect(mode="prematch")
    return {"provider": "odds_api", "mode": "prematch", "total": result.records_collected}

@safe_job
async def fixtures_weekly():
    """
    Trigger: `0 5 * * 1`
    Objetivo: Atualizar calendário semanal. API-Football Discovery para pareamento de IDs externos.
    """
    now = datetime.now(timezone.utc)
    date_from = now.strftime('%Y-%m-%d')
    date_to = (now + timedelta(days=7)).strftime('%Y-%m-%d')
    
    collector = ApiFootballCollector()
    result = await collector.collect(mode="discovery", date_from=date_from, date_to=date_to)
    return {"provider": "api_football", "job": "fixtures_weekly", "total": result.records_collected}


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

async def _run_prematch_tracker(phase: str):
    import subprocess
    import sys

    try:
        logger.info(f"spawning_prematch_tracker_subprocess_phase_{phase}")
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/run_flashscore_prematch.py", "--phase", phase,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()

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
async def prematch_tracking_morning():
    return await _run_prematch_tracker("tracking_2x")

@safe_job
async def prematch_tracking_evening():
    return await _run_prematch_tracker("tracking_2x")

@safe_job
async def flashscore_complementary():
    """
    Objetivo: Rescrape complementar de faltantes.
    """
    import subprocess
    import sys

    try:
        logger.info("spawning_flashscore_complementary_subprocess")
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/run_flashscore_complementary.py", "--limit", "250",
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
async def odds_single_match(match_id: str, label: str):
    """
    Coleta odds de um jogo específico próximo ao kickoff.
    Usado no dinamismo T-60, T-30, etc.
    """
    collector = OddsApiCollector()
    result = await collector.collect(mode="single_match", match_id=match_id)
    return {"match_id": match_id, "label": label, "total": result.records_collected}

@safe_job
async def lineups_single_match(match_id: str):
    """
    Extrai lineups confirmadas T-60.
    """
    collector = ApiFootballCollector()
    result = await collector.collect(mode="lineup", match_id=match_id)
    return {"match_id": match_id, "total": result.records_collected}

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
            (-60, "pre60_lineups", lineups_single_match),
            # Desativados os triggers Odds API enquanto o pipeline backfill avança
            # (-60, "pre60_odds", odds_single_match),
            # (-30, "pre30_odds", odds_single_match),
            # (-5, "pre5_odds", odds_single_match),
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
            if job_func == odds_single_match:
                kwargs["label"] = label
            elif job_func == flashscore_dynamic_prematch:
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
    Lê estado local e consome até ~650 requisições diárias.
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
    import subprocess
    import sys
    import random
    import re
    
    # Servidores homologados para rodízio (6 servidores)
    servers = ["br89", "br105", "br75", "br116", "br76", "br81"]
    target_server = random.choice(servers)
    
    # 1. Tentar rotacionar o IP via NordVPN
    try:
        logger.info("nordvpn_connecting", server=target_server)
        res = subprocess.run(["nordvpn", "connect", target_server], check=True, capture_output=True, text=True)
        
        # Puxa o status real para inspecionar o IP
        status_res = subprocess.run(["nordvpn", "status"], capture_output=True, text=True)
        ip_match = re.search(r"\bIP:\s*([\d\.]+)", status_res.stdout)
        new_ip = ip_match.group(1) if ip_match else "Desconhecido"
        
        logger.info("nordvpn_reconnected", server=target_server, ip=new_ip)
        # Dispara sucesso para o Telegram
        TelegramAlert.fire("info", f"🔄 Rodízio de IP (NordVPN)\nSrv: `{target_server}`\nIP: `{new_ip}`")
        
    except FileNotFoundError:
        logger.warning("nordvpn_binary_not_found_skipping_rotation")
    except subprocess.CalledProcessError as e:
        logger.error("nordvpn_failed", error=e.stderr.strip())
        TelegramAlert.fire("warning", f"NordVPN rodízio falhou no srv {target_server}:\n{e.stderr.strip()}")

    # Janela de tempo por execução (horas). O filho para sozinho nesse limite;
    # o pai tem um guard de +6 min para não bloquear o orchestrator para sempre.
    WINDOW_HOURS = 2.4
    GUARD_SECONDS = int(WINDOW_HOURS * 3600) + 360  # +6 min de margem

    # 2. Spawn subprocess para limpar memória após a execução (o browser come muito)
    try:
        logger.info("spawning_flashscore_backfill_subprocess", timeout_hours=WINDOW_HOURS)
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/run_flashscore_backfill.py",
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

    except RuntimeError:
        raise  # Re-propagado para o safe_job capturar e notificar Telegram
    except Exception as e:
        logger.error("flashscore_backfill_spawn_failed", error=str(e))
        raise

    return {"job": "flashscore_historical_backfill", "records_count": records_count}


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
async def odds_api_validation(): pass

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
        "🗓 *Rotinas Fixas de hoje:*",
        "  `00:20` — Data Quality Routine",
        "  `00:30` — Schedule Gameday Dinâmico",
        "  `00:40` — Flashscore Backfill (janela 1)",
        "  `03:15` — Heartbeat / Notificações",
        "  `03:20` — API-Football Backfill",
        "  `04:00` — FootyStats Daily",
        "  `04:10` — Football-Data Daily",
        "  `04:20` — 💾 Backup DB → OneDrive",
        "  `05:25` — Flashscore Discovery Fixtures",
        "  `05:50` — Flashscore Discovery Results",
        "  `06:15` — Flashscore Backfill (janela 2)",
        "  `08:50` — Flashscore Backfill (janela 3)",
        "  `11:25` — Flashscore Backfill (janela 4)",
        "  `14:00` — Flashscore Backfill (janela 5)",
        "  `16:35` — Flashscore Prematch Tracking",
        "  `19:10` — Flashscore Backfill (janela 6)",
        "  `21:45` — Flashscore Backfill (janela 7)",
        "  `23:50` — Reset Daily Keys"
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
                    ms.match_id,
                    MAX(CASE WHEN ms.shots_home IS NOT NULL THEN 1 ELSE 0 END) AS has_footystats_stats,
                    MAX(CASE WHEN ms.total_passes_home IS NOT NULL OR ms.expected_goals_home IS NOT NULL THEN 1 ELSE 0 END) AS has_apifootball_stats,
                    MAX(CASE WHEN ms.xg_fs_home IS NOT NULL OR ms.xgot_fs_home IS NOT NULL THEN 1 ELSE 0 END) AS has_flashscore_stats
                FROM match_stats ms
                GROUP BY ms.match_id
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
        
        tg_msg = [
            f"📊 *Data Quality Report — {today_str}*",
            f"Jogos finalizados analisados: `{total_matches}`",
            "",
            "✅ *Cobertura Geral:*",
            f"  FootyStats:  `{totals_row['footystats_stats']}/{total_matches} ({pct(totals_row['footystats_stats'])}%)`",
            f"  APIFootball:  `{totals_row['apifootball_stats']}/{total_matches} ({pct(totals_row['apifootball_stats'])}%)`",
            f"  FlashScore:   `{totals_row['flashscore_stats']}/{total_matches} ({pct(totals_row['flashscore_stats'])}%)`",
            f"  FD Odds:      `{totals_row['football_data_odds']}/{total_matches} ({pct(totals_row['football_data_odds'])}%)`",
            f"  FS Odds:      `{totals_row['flashscore_odds']}/{total_matches} ({pct(totals_row['flashscore_odds'])}%)`",
            "",
            "🔍 *Auditoria de Odds:*",
            f"  Odds 1x2 suspeitas: `{totals_row['susp_1x2']}/{total_matches} ({pct(totals_row['susp_1x2'])}%)`",
            f"  Odds OU suspeitas:  `{totals_row['susp_ou']}/{total_matches} ({pct(totals_row['susp_ou'])}%)`",
            f"  Odds AH suspeitas:  `{totals_row['susp_ah']}/{total_matches} ({pct(totals_row['susp_ah'])}%)`",
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
                tg_msg.append(f"  {row['league_code']} {row['season']}: `{row['total_issues']} jogos com falhas`")
        else:
            tg_msg.append("🎉 *Todas as ligas estão 100% completas!*")
            
        tg_msg.append("")
        tg_msg.append("🔗 _Relatório completo salvo no log._")
        
        # 4. Notificar via telegram
        TelegramAlert.fire("info", "\n".join(tg_msg))
        
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

        return {"total_matches": total_matches, "jobs": "run_data_quality_routine"}

