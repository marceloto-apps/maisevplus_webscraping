import os
import asyncio
from collections import deque
from time import monotonic
from typing import Optional

import httpx

from src.db.logger import get_logger

logger = get_logger(__name__)

LEVEL_EMOJI = {
    "info":     "✅",
    "success":  "🎉",
    "warning":  "⚠️",
    "error":    "❌",
    "critical": "🔥",
}

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

class RateLimiter:
    def __init__(self, max_calls: int = 20, period: float = 60.0):
        self._calls: deque[float] = deque()
        self._max = max_calls
        self._period = period

    def allow(self) -> bool:
        now = monotonic()
        self._purge(now)
        if len(self._calls) >= self._max:
            return False
        self._calls.append(now)
        return True

    def seconds_until_free(self) -> Optional[float]:
        now = monotonic()
        self._purge(now)
        if len(self._calls) < self._max:
            return None
        return self._period - (now - self._calls[0])

    def _purge(self, now: float):
        while self._calls and self._calls[0] < now - self._period:
            self._calls.popleft()


class TelegramAlert:
    _client: Optional[httpx.AsyncClient] = None
    _token: Optional[str] = None
    _chat_id: Optional[str] = None
    _enabled: bool = False
    _limiter: RateLimiter = RateLimiter(max_calls=20, period=60.0)
    _pending_tasks: set = set()  # rastreia tasks fire-and-forget em voo

    @classmethod
    async def init(cls):
        cls._token = os.getenv("TELEGRAM_BOT_TOKEN")
        cls._chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not cls._token or not cls._chat_id:
            logger.info("telegram_alerts_disabled")
            cls._enabled = False
            return
        cls._client = httpx.AsyncClient(timeout=10)
        cls._enabled = True
        logger.info("telegram_alerts_enabled")

    @classmethod
    async def close(cls):
        # Aguarda todas as tasks de envio em voo antes de fechar o client.
        # Sem isso, o client é destruído antes do último fire() ser entregue.
        if cls._pending_tasks:
            await asyncio.gather(*cls._pending_tasks, return_exceptions=True)
            cls._pending_tasks.clear()
        if cls._client:
            await cls._client.aclose()
            cls._client = None
        cls._enabled = False

    @classmethod
    def fire(cls, level: str, message: str):
        """Fire-and-forget. Nunca bloqueia, nunca propaga exceção."""
        if not cls._enabled or level not in LEVEL_EMOJI:
            return
        if not cls._limiter.allow():
            wait = cls._limiter.seconds_until_free()
            logger.debug("telegram_throttled", wait_s=round(wait or 0, 1))
            return
        task = asyncio.create_task(cls._send(level, message))
        cls._pending_tasks.add(task)
        task.add_done_callback(cls._pending_tasks.discard)  # remove ao concluir
        task.add_done_callback(cls._handle_task_error)

    @classmethod
    async def _send(cls, level: str, message: str):
        emoji = LEVEL_EMOJI.get(level, "ℹ️")
        text = f"{emoji} *[{level.upper()}]*\n\n{message}"
        # Telegram rejeita mensagens acima de 4096 chars com 400 Bad Request.
        # Truncamos com aviso para garantir a entrega.
        MAX_CHARS = 4000
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "\n\n_...mensagem truncada..._"
        url = TELEGRAM_API.format(token=cls._token)
        payload = {
            "chat_id": cls._chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        try:
            resp = await cls._client.post(url, json=payload)
            resp.raise_for_status()
        except Exception:
            # Re-raise para o _handle_task_error capturar e logar
            raise

    @staticmethod
    def _handle_task_error(task: asyncio.Task):
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            logger.error(
                "telegram_send_failed",
                error=type(exc).__name__,
                detail=str(exc),
                status_code=status_code,
            )
