"""
T04 — src/alerts/telegram_mini.py

Placeholder do sistema de alertas. Interface final definida agora para que
os 6+ coletores chamem a mesma assinatura — a T13 só troca o corpo.

Níveis: 'info' (apenas log), 'warning', 'error', 'critical'
"""

import os
from ..db.logger import get_logger

logger = get_logger(__name__)

# Will be populated in T13 with the real Telegram Bot API implementation
_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")


async def send_alert(message: str, level: str = "warning") -> None:
    """
    Envia um alerta para o canal de monitoramento configurado.

    Args:
        message: Texto descritivo do evento (ex: "FlashScore timeout após 3 retries")
        level:   'info' | 'warning' | 'error' | 'critical'

    Comportamento atual (Placeholder T04):
        Apenas loga. Backfill seguro sem dependências externas.

    Comportamento futuro (T13):
        httpx POST para Telegram Bot API com formatação de nível.
    """
    log_fn = {
        "info":     logger.info,
        "warning":  logger.warning,
        "error":    logger.error,
        "critical": logger.critical,
    }.get(level, logger.warning)

    log_fn("alert", level=level, message=message)

    # T13: implementar aqui o httpx.post() para o Telegram
