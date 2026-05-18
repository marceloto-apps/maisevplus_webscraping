import asyncio
import os
import argparse
from dotenv import load_dotenv
from src.db.pool import get_pool, close_pool
from src.db.logger import get_logger
from src.alerts.telegram_mini import TelegramAlert

load_dotenv()
logger = get_logger(__name__)

# Jogo real da Premier League para teste ativo (caso seja necessário validar scraping isolado)
CANARY_MATCH_URL = os.getenv(
    "CANARY_MATCH_URL",
    "https://www.flashscore.com/match/lSfM9N75/"  # fallback: Aston Villa vs Chelsea
)

async def run_canary(threshold: float):
    logger.info("Iniciando verificação de saúde do Flashscore (Canary)...")
    await TelegramAlert.init()
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Pega a última métrica inserida
        row = await conn.fetchrow('''
            SELECT * FROM scraping_health
            WHERE source = 'flashscore'
            ORDER BY run_ts DESC
            LIMIT 1
        ''')
        
        if not row:
            logger.info("Nenhuma métrica encontrada para flashscore.")
            await close_pool()
            await TelegramAlert.close()
            return
            
        success_rate = float(row['success_rate'])
        total_processed = row['total_matches']
        
        # Só alerta se processou pelo menos 10 jogos (evita falso positivo em lote pequeno)
        if total_processed >= 10 and success_rate < threshold:
            msg = (
                f"🚨 *ALERTA CRÍTICO: DEGRADAÇÃO DOM FLASHSCORE* 🚨\n\n"
                f"A taxa de sucesso da última coleta despencou!\n"
                f"**Taxa atual:** {success_rate:.1%} (Abaixo do limiar de {threshold}%)\n"
                f"**Nível:** {row['alert_level']}\n"
                f"**Jogos Processados:** {total_processed}\n"
                f"**Bet365 Encontrada:** {row['bet365_found']} vezes\n"
                f"**Bookmakers Médios:** {float(row['avg_bookmakers']):.1f}\n\n"
                f"⚠️ O DOM do Flashscore pode ter mudado. Execute teste ativo em {CANARY_MATCH_URL}!"
            )
            logger.error(f"Degradação detectada! Taxa: {success_rate:.1f}%")
            try:
                TelegramAlert.fire("critical", msg)
            except Exception as e:
                logger.error(f"Falha ao enviar alerta Telegram: {e}")
        else:
            logger.info(f"Saúde do Flashscore OK: {success_rate:.1f}% em {total_processed} jogos.")
            
    await close_pool()
    await TelegramAlert.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verifica a saúde do scraping do Flashscore.")
    parser.add_argument("--threshold", type=float, default=30.0, help="Limiar de sucesso em %% para disparar alerta.")
    args = parser.parse_args()
    
    asyncio.run(run_canary(args.threshold))
