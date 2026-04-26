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
    set_scheduler,
    run_data_quality_routine,
    db_backup,
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
        from src.scheduler.jobs import flashscore_complementary
        set_scheduler(self.scheduler)
        
        # 00:20 - Data Quality Routine
        self.scheduler.add_job(
            run_data_quality_routine,
            'cron',
            hour=0, minute=20,
            id="data_quality_routine",
            misfire_grace_time=3600
        )

        # 00:30 - Schedule Dinâmico
        self.scheduler.add_job(
            schedule_gameday_jobs,
            'cron',
            hour=0, minute=30,
            id="schedule_gameday_jobs",
            misfire_grace_time=1800
        )

        # 00:40 - Flashscore Backfill (janela 1)
        self.scheduler.add_job(
            flashscore_historical_backfill,
            'cron',
            hour=0, minute=40,
            id="flashscore_backfill_1",
            misfire_grace_time=3600
        )

        # 03:15 - Health Check / Heartbeat Diário
        self.scheduler.add_job(
            health_check,
            'cron',
            hour=3, minute=15,
            id="daily_heartbeat",
            misfire_grace_time=3600
        )

        # 03:20 - API-Football Backfill
        self.scheduler.add_job(
            apifootball_backfill,
            'cron',
            hour=3, minute=20,
            id="apifootball_backfill",
            misfire_grace_time=7200
        )

        # 04:00 - FootyStats Daily
        self.scheduler.add_job(
            footystats_daily,
            'cron',
            hour=4, minute=0,
            id="footystats_daily",
            misfire_grace_time=7200
        )

        # 04:10 - Football-Data Daily
        self.scheduler.add_job(
            football_data_daily,
            'cron',
            hour=4, minute=10,
            id="football_data_daily",
            misfire_grace_time=7200
        )

        # 04:20 - Backup DB → OneDrive
        self.scheduler.add_job(
            db_backup,
            'cron',
            hour=4, minute=20,
            id="db_backup",
            misfire_grace_time=3600
        )

        # 05:25 - Flashscore Discovery Fixtures
        self.scheduler.add_job(
            flashscore_discovery_fixtures,
            'cron',
            hour=5, minute=25,
            id="flashscore_discovery_fixtures",
            misfire_grace_time=1800,
            replace_existing=True
        )

        # 05:50 - Flashscore Discovery Results
        self.scheduler.add_job(
            flashscore_discovery,
            'cron',
            hour=5, minute=50,
            id="flashscore_discovery",
            misfire_grace_time=7200
        )

        # 06:15 - Flashscore Backfill (janela 2)
        self.scheduler.add_job(
            flashscore_historical_backfill,
            'cron',
            hour=6, minute=15,
            id="flashscore_backfill_2",
            misfire_grace_time=3600
        )

        # 08:50 - Flashscore Backfill (janela 3)
        self.scheduler.add_job(
            flashscore_historical_backfill,
            'cron',
            hour=8, minute=50,
            id="flashscore_backfill_3",
            misfire_grace_time=3600
        )
        
        # 11:25 - Flashscore Backfill (janela 4)
        self.scheduler.add_job(
            flashscore_historical_backfill,
            'cron',
            hour=11, minute=25,
            id="flashscore_backfill_4",
            misfire_grace_time=3600
        )

        # 14:00 - Flashscore Backfill (janela 5)
        self.scheduler.add_job(
            flashscore_historical_backfill,
            'cron',
            hour=14, minute=0,
            id="flashscore_backfill_5",
            misfire_grace_time=3600
        )

        # 16:35 - Flashscore Prematch Tracking
        self.scheduler.add_job(
            prematch_tracking_morning,
            'cron',
            hour=16, minute=35,
            id="prematch_tracking",
            misfire_grace_time=1800,
            replace_existing=True
        )

        # 19:10 - Flashscore Backfill (janela 6)
        self.scheduler.add_job(
            flashscore_historical_backfill,
            'cron',
            hour=19, minute=10,
            id="flashscore_backfill_6",
            misfire_grace_time=3600
        )
        
        # 21:45 - Flashscore Backfill (janela 7)
        self.scheduler.add_job(
            flashscore_historical_backfill,
            'cron',
            hour=21, minute=45,
            id="flashscore_backfill_7",
            misfire_grace_time=3600
        )

        # 23:50 - Reset Keys (BRT)
        self.scheduler.add_job(
            reset_daily_keys,
            'cron',
            hour=23, minute=50,
            id="reset_daily_keys",
            misfire_grace_time=3600
        )
        
        # KeyManager Reset Monthly (dia 1 à meia-noite UTC = 21:00 BRT) -> preservado como UTC just in case.
        self.scheduler.add_job(
            reset_monthly_keys,
            'cron',
            timezone=ZoneInfo("UTC"),
            day=1, hour=0, minute=0,
            id="reset_monthly_keys",
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
