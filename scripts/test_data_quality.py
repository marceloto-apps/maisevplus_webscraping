import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from src.db.pool import get_pool, close_pool
from src.alerts.telegram_mini import TelegramAlert
from src.scheduler.jobs import run_data_quality_routine

async def test_run():
    print("Iniciando rotina de Data Quality Audit...")
    await TelegramAlert.init()
    res = await run_data_quality_routine()
    print('✅ Rotina executada. Resultado:', res)
    
    # Aguarda o dispatch assíncrono do Telegram finalizar
    running = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if running:
        print("Aguardando envio do Telegram...")
        await asyncio.wait(running, timeout=10)
        
    await TelegramAlert.close()
    await close_pool()
    print("Processo finalizado!")

if __name__ == "__main__":
    asyncio.run(test_run())
