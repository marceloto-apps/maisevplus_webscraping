import asyncio
import signal
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.db.pool import get_pool, close_pool
from src.db.logger import get_logger
from src.alerts.telegram_mini import TelegramAlert
from src.config.loader import ConfigLoader
from src.normalizer.team_resolver import TeamResolver
from src.scheduler.jobs import (
    odds_standard,
    odds_gameday_hourly,
    fixtures_weekly,
    footystats_daily,
    football_data_daily,
    apifootball_backfill,
    reset_daily_keys,
    reset_monthly_keys,
    schedule_gameday_jobs,
    flashscore_discovery,
    flashscore_odds_standard,
    flashscore_closing_odds,
    flashscore_historical_backfill,
    flashscore_discovery_fixtures,
    prematch_tracking_morning,
    prematch_tracking_evening,
    health_check,
    health_check,
    set_scheduler
)

logger = get_logger(__name__)

class AppOrchestrator:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=ZoneInfo("America/Sao_Paulo"))
        self._shutdown_event = asyncio.Event()

    def _signal_handler(self, sig):
        """Callback de interrupção (OS signals)."""
        logger.info("shutdown_signal_received", signal=sig.name)
        self._shutdown_event.set()

    def _setup_routing(self):
        """Registra os jobs fixos e periódicos na instância da APScheduler."""
        set_scheduler(self.scheduler)
        # 1. Odds Gameday Hourly (apenas janela 8-23h BRT)
        # self.scheduler.add_job(
        #     odds_gameday_hourly,
        #     'cron',
        #     hour='8-23', minute=0,
        #     id="odds_gameday_hourly",
        #     misfire_grace_time=3600
        # )

        # 2. KeyManager Reset Daily (sempre à meia-noite UTC = 21:00 BRT)
        self.scheduler.add_job(
            reset_daily_keys,
            'cron',
            timezone=ZoneInfo("UTC"),
            hour=0, minute=0,
            id="reset_daily_keys",
            misfire_grace_time=3600
        )

        # 3. KeyManager Reset Monthly (dia 1 à meia-noite UTC)
        self.scheduler.add_job(
            reset_monthly_keys,
            'cron',
            timezone=ZoneInfo("UTC"),
            day=1, hour=0, minute=0,
            id="reset_monthly_keys",
            misfire_grace_time=3600
        )

        # 4. Schedule Dinâmico (00:30 BRT)
        self.scheduler.add_job(
            schedule_gameday_jobs,
            'cron',
            hour=0, minute=30,
            id="schedule_gameday_jobs",
            misfire_grace_time=1800
        )

        # 4. Odds Standard para D+1 a D+7 (06:00, 10:00, 14:00, 20:00 BRT)
        # self.scheduler.add_job(
        #     odds_standard,
        #     'cron',
        #     hour='6,10,14,20', minute=0,
        #     id="odds_standard",
        #     misfire_grace_time=3600
        # )

        # 5. FootyStats Daily — 04:10 BRT (atualiza temporadas ativas + auto-close)
        self.scheduler.add_job(
            footystats_daily,
            'cron',
            hour=4, minute=10,
            id="footystats_daily",
            misfire_grace_time=7200
        )

        # 6. Football-Data Daily — 04:20 BRT (atualiza CSVs das temporadas ativas)
        self.scheduler.add_job(
            football_data_daily,
            'cron',
            hour=4, minute=20,
            id="football_data_daily",
            misfire_grace_time=7200
        )

        # 6b. API-Football Backfill — 03:20 BRT (garante VPN desconectada do Flashscore das 01h)
        self.scheduler.add_job(
            apifootball_backfill,
            'cron',
            hour=3, minute=20,
            id="apifootball_backfill",
            misfire_grace_time=7200
        )

        # 6c. Flashscore Historical Backfill — 7 janelas BRT (ip rotation a cada rodada)
        # Minuto :00  → 01h, 08h, 15h, 22h
        self.scheduler.add_job(
            flashscore_historical_backfill,
            'cron',
            hour='1,8,15,22', minute=0,
            id="flashscore_backfill_m00",
            misfire_grace_time=3600
        )
        # Minuto :20  → 10h20, 17h20
        self.scheduler.add_job(
            flashscore_historical_backfill,
            'cron',
            hour='10,17', minute=20,
            id="flashscore_backfill_m20",
            misfire_grace_time=3600
        )
        # Minuto :40  → 12h40
        self.scheduler.add_job(
            flashscore_historical_backfill,
            'cron',
            hour=12, minute=40,
            id="flashscore_backfill_m40",
            misfire_grace_time=3600
        )

        # 7. Fixtures Weekly (Segundas-feiras 05:00 BRT — calendário futuro via API-Football)
        # self.scheduler.add_job(
        #     fixtures_weekly,
        #     'cron',
        #     day_of_week='mon', hour=5, minute=0,
        #     id="fixtures_weekly",
        #     misfire_grace_time=7200
        # )

        # 8. Flashscore Discovery (05:00 BRT — descobre match IDs passados)
        self.scheduler.add_job(
            flashscore_discovery,
            'cron',
            hour=5, minute=0,
            id="flashscore_discovery",
            misfire_grace_time=7200
        )

        # 9. Flashscore Odds Standard (07:00, 11:00, 15:00, 21:00 BRT)
        # self.scheduler.add_job(
        #     flashscore_odds_standard,
        #     'cron',
        #     hour='7,11,15,21', minute=0,
        #     id="flashscore_odds_standard",
        #     misfire_grace_time=3600
        # )
        
        # 9b. Flashscore Discovery Fixtures (04:30 BRT)
        self.scheduler.add_job(
            flashscore_discovery_fixtures,
            'cron',
            hour=4, minute=30,
            id="flashscore_discovery_fixtures",
            misfire_grace_time=1800,
            replace_existing=True
        )

        # 9c. Flashscore Prematch Tracking Morning (05:40 BRT)
        self.scheduler.add_job(
            prematch_tracking_morning,
            'cron',
            hour=5, minute=40,
            id="prematch_tracking_morning",
            misfire_grace_time=1800,
            replace_existing=True
        )

        # 9d. Flashscore Prematch Tracking Evening (19:40 BRT)
        self.scheduler.add_job(
            prematch_tracking_evening,
            'cron',
            hour=19, minute=40,
            id="prematch_tracking_evening",
            misfire_grace_time=1800,
            replace_existing=True
        )

        # 10. Flashscore Closing Odds (06:30 BRT — odds de fechamento de D-1)
        # self.scheduler.add_job(
        #     flashscore_closing_odds,
        #     'cron',
        #     hour=6, minute=30,
        #     id="flashscore_closing_odds",
        #     misfire_grace_time=3600
        # )

        # 11. Health Check / Heartbeat Diário (03:00 BRT)
        # Confirma no Telegram que o orchestrator está vivo e lista os próximos jobs.
        self.scheduler.add_job(
            health_check,
            'cron',
            hour=3, minute=0,
            id="daily_heartbeat",
            misfire_grace_time=3600
        )

    async def _init_dependencies(self):
        """Prepara DB e Caches síncronas antes do start loop"""
        logger.info("app_init_started")
        await get_pool()
        await ConfigLoader.load_leagues()
        await TeamResolver.load_cache()
        await TelegramAlert.init()
        logger.info("app_dependencies_ready")


    async def _cleanup(self):
        """Graceful shutdown dos buffers e conexões ativas"""
        logger.info("app_cleanup_started")
        
        # Para novas agitações na engine do Scheduler
        self.scheduler.shutdown(wait=False)

        # Aguardar jobs ativos terminarem (com timeout)
        running = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if running:
            logger.info("waiting_running_tasks", count=len(running))
            await asyncio.wait(running, timeout=30)

        # Tenta disparar a inserção de resolvers unknown se haviam remanescentes em memória.
        try:
            await TeamResolver.flush_unknowns()
        except Exception as e:
            logger.error("app_cleanup_flush_failed", error=str(e))
        
        await TelegramAlert.close()
        await close_pool()
        logger.info("app_cleanup_finished")

    async def run_forever(self):
        """Loop principal do Evento. Retém a pool e escuta OS SIGTERMs"""
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_handler, sig)

        await self._init_dependencies()
        self._setup_routing()
        
        self.scheduler.start()
        logger.info("scheduler_started")

        # Segura a execução até sinal de kill chegar no App.
        await self._shutdown_event.wait()
        
        # Sinal ocorreu — cleanup lifecycle sequence
        await self._cleanup()


if __name__ == "__main__":
    orchestrator = AppOrchestrator()
    try:
        asyncio.run(orchestrator.run_forever())
    except KeyboardInterrupt:
        pass
