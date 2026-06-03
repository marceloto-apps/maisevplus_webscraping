import asyncio
import os
import sys
import json
import subprocess
from datetime import datetime, timezone

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.alerts.telegram_mini import TelegramAlert
from src.db.logger import configure_logging, get_logger

configure_logging()
logger = get_logger("check_backfill_status")

def get_process_running_linux() -> bool:
    """Verifica se o processo do backfill está rodando no Linux."""
    try:
        res = subprocess.run(["pgrep", "-f", "run_sequential_backfill.py"], capture_output=True, text=True)
        return res.returncode == 0
    except Exception as e:
        logger.error("failed_to_run_pgrep", error=str(e))
        return False

async def main():
    await TelegramAlert.init()
    
    status_file = os.path.join(os.getcwd(), "logs", "backfill_status.json")
    if not os.path.exists(status_file):
        logger.warning("status_file_not_found")
        await TelegramAlert.close()
        return

    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("failed_to_read_status_file", error=str(e))
        await TelegramAlert.close()
        return

    status = data.get("status")
    last_run_started = data.get("last_run_started")
    last_error = data.get("last_error")
    all_completed_notified = data.get("all_completed_notified", False)
    error_notified = data.get("error_notified", False)
    interrupted_notified = data.get("interrupted_notified", False)

    # 1. Checar se o serviço systemd maisevplus está ativo (apenas Linux)
    service_ok = True
    service_status = "unknown"
    if sys.platform.startswith("linux"):
        try:
            res = subprocess.run(["systemctl", "is-active", "maisevplus"], capture_output=True, text=True)
            service_status = res.stdout.strip()
            if service_status != "active":
                service_ok = False
        except Exception as e:
            logger.warning("failed_to_check_systemd_service", error=str(e))

    if not service_ok:
        msg = f"❌ *Serviço maisevplus inativo*\nO serviço systemd está com status: `{service_status}`. Reinicie-o na VPS."
        TelegramAlert.fire("critical", msg)
        logger.error("maisevplus_service_inactive", status=service_status)

    # 2. Consultar o banco para ver se há trabalho pendente
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Partidas de todas as ligas ativas que ainda precisam de scraping de odds/stats no Flashscore
        pending_matches = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            WHERE l.is_active = TRUE
              AND m.status = 'finished'
              AND m.flashscore_id IS NOT NULL
              AND (m.scraping_flashscore IS NULL OR m.scraping_flashscore = FALSE)
              AND (m.flashscore_stats_collected = FALSE OR m.flashscore_odds_collected = FALSE)
        """)
        # Aliases de times do flashscore ainda não resolvidos
        unresolved_aliases = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM unknown_aliases 
            WHERE source = 'flashscore' AND resolved = FALSE
        """)

    # 3. Tratar caso: Tudo concluído
    if pending_matches == 0 and unresolved_aliases == 0:
        if not all_completed_notified:
            msg = (
                "🎉 *Backfill Flashscore Concluído*\n"
                "O processo de backfill do Flashscore não está rodando porque *todas as ligas e temporadas foram finalizadas com sucesso*!\n\n"
                "📊 *Resumo:*\n"
                "- Partidas pendentes de odds/stats: 0\n"
                "- Aliases pendentes: 0"
            )
            TelegramAlert.fire("success", msg)
            logger.info("all_backfill_completed_notification_sent")
            # Salva no arquivo que já notificou
            data["all_completed_notified"] = True
            try:
                with open(status_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error("failed_to_write_status_file", error=str(e))
    else:
        # Se existem pendências, reseta a flag para podermos notificar de novo quando terminar no futuro
        if all_completed_notified:
            data["all_completed_notified"] = False
            try:
                with open(status_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error("failed_to_write_status_file", error=str(e))

    # 4. Checar status e possíveis erros/travamentos
    status_changed = False

    if status == "error":
        if not error_notified:
            msg = f"❌ *Erro no Backfill do Flashscore*\nO último processo de backfill terminou com erro.\n\n*Detalhes:* `{last_error}`"
            TelegramAlert.fire("error", msg)
            logger.error("backfill_last_run_had_error", error=last_error)
            data["error_notified"] = True
            status_changed = True

    elif status == "running":
        duration_hours = 0.0
        if last_run_started:
            try:
                started_dt = datetime.fromisoformat(last_run_started)
                # Garante timezone UTC
                if started_dt.tzinfo is None:
                    started_dt = started_dt.replace(tzinfo=timezone.utc)
                else:
                    started_dt = started_dt.astimezone(timezone.utc)
                
                duration = datetime.now(timezone.utc) - started_dt
                duration_hours = duration.total_seconds() / 3600
            except Exception as e:
                logger.error("failed_to_calculate_running_duration", error=str(e))

        # Checar se consta rodando mas o processo morreu silenciosamente (apenas Linux)
        is_running_os = True
        if sys.platform.startswith("linux"):
            is_running_os = get_process_running_linux()

        # Só considera interrompido por ausência de processo se já passou de 10 minutos do início
        if not is_running_os and duration_hours * 60.0 > 10.0:
            if not interrupted_notified:
                msg = "⚠️ *Backfill Flashscore Interrompido*\nO status consta como executando, mas o processo `run_sequential_backfill.py` não foi encontrado rodando no sistema operacional."
                TelegramAlert.fire("warning", msg)
                logger.warning("backfill_running_status_but_no_process")
                data["interrupted_notified"] = True
                data["status"] = "interrupted"
                data["last_run_finished"] = datetime.now(timezone.utc).isoformat()
                data["last_error"] = "Processo run_sequential_backfill.py não encontrado rodando no SO."
                status_changed = True
        elif duration_hours > 3.0:
            if not interrupted_notified:
                msg = f"⚠️ *Backfill Flashscore Travado (Suspeito)*\nO processo iniciou há `{duration_hours:.1f}` horas e ainda consta como executando. Possível travamento."
                TelegramAlert.fire("warning", msg)
                logger.warning("backfill_running_too_long", hours=duration_hours)
                data["interrupted_notified"] = True
                data["status"] = "interrupted"
                data["last_run_finished"] = datetime.now(timezone.utc).isoformat()
                data["last_error"] = f"Processo travado ou rodando por tempo excessivo ({duration_hours:.1f}h)."
                status_changed = True

    if status_changed:
        try:
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("failed_to_write_status_file", error=str(e))

    await pool.close()
    await TelegramAlert.close()

if __name__ == "__main__":
    asyncio.run(main())
