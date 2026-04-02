"""
Sobe o orchestrator real por 60 segundos.
Substitui os crons originais por um disparo a cada 10s, validando o ciclo completo
e forçando um alert do Telegram para atestar a comunicação.
"""
import asyncio
import logging
from src.scheduler.orchestrator import AppOrchestrator
from src.scheduler.jobs import safe_job, set_scheduler
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(level=logging.DEBUG)

@safe_job
async def dummy_test_job():
    print("Dummy Job Rodando...")
    # Lançar exceção a cada 3 chamadas não afeta mas suja
    pass

@safe_job
async def poison_job():
    raise Exception("Dry Run Poison Event (Isso deve gerar alert no Telegram!)")

class DryRunOrchestrator(AppOrchestrator):
    def _setup_routing(self):
        set_scheduler(self.scheduler)
        self.scheduler.add_job(dummy_test_job, IntervalTrigger(seconds=10), id="dummy_1")
        # Dispara log fatal depois de 15 segundos
        self.scheduler.add_job(poison_job, 'date', run_date=None, id="poison_1") # Date triggering defaults to now

async def main():
    orch = DryRunOrchestrator()
    
    # Executamos o init para injetar o DB, telegram_mini, e logs
    await orch._init_dependencies()
    orch._setup_routing()
    
    orch.scheduler.start()
    
    # Roda por 60s
    await asyncio.sleep(60)
    
    # Chama o cleanup graciosamente
    await orch._cleanup()
    print("\n✅ Orchestrator rodou 60s e aplicou Shutdown.")

if __name__ == "__main__":
    asyncio.run(main())
