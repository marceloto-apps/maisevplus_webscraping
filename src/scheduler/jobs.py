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
            (-60, "pre60_odds", odds_single_match),
            (-30, "pre30_odds", odds_single_match),
            (-5, "pre5_odds", odds_single_match),
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
    Trigger: `0 2 * * *` BRT
    Objetivo: Backfill reversivo das temporadas atuais (a partir de 03/04).
    Lê estado local e consome até ~650 requisições diárias.
    """
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
    
    # Servidores homologados para rodízio
    servers = ["br89", "br105", "br75"]
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

    # 2. Spawn subprocess para limpar memória após a execução (o browser come muito)
    try:
        logger.info("spawning_flashscore_backfill_subprocess")
        proc = await asyncio.create_subprocess_exec(
            "xvfb-run", "-a", sys.executable, "scripts/run_flashscore_backfill.py", "--limit", "180",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()

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
        "🗓 *Rotinas de hoje:*",
        "  `02:00` — Flashscore Backfill (janela 1)",
        "  `04:00` — API-Football Backfill",
        "  `05:00` — FootyStats Daily",
        "  `05:15` — Football-Data Daily",
        "  `06:00` — Flashscore Discovery",
        "  `06:15` — Flashscore Backfill (janela 2)",
        "  `09:00` — Flashscore Backfill (janela 3)",
        "  `12:00` — Flashscore Backfill (janela 4)",
        "  `15:00` — Flashscore Backfill (janela 5)",
        "  `18:00` — Flashscore Backfill (janela 6)",
        "  `21:00` — Flashscore Backfill (janela 7)",
    ]
    if is_monday:
        schedule_lines.append("  `05:00` — Fixtures Weekly *(segunda-feira)*")

    schedule_txt = "\n".join(schedule_lines)

    TelegramAlert.fire(
        "info",
        f"💓 *Orchestrator Alive*\n"
        f"{weekday_pt}, {today_str} — 03:00 BRT\n\n"
        f"{schedule_txt}"
    )

    return {"heartbeat": True}

