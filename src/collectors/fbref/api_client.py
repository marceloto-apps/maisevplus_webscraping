"""
T08 — FBRef API Client
Rate limit defensivo: Semaphore(1) + cooldown 4.0s + backoff exponencial em 429.
"""
import asyncio
import httpx
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

from ...db.logger import get_logger

logger = get_logger(__name__)


class RateLimitedException(Exception):
    pass


class FBRefClient:
    def __init__(self, timeout: int = 20, cooldown: float = 4.0):
        self.semaphore = asyncio.Semaphore(1)
        self.cooldown = cooldown
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "Accept-Language": "en-US,en;q=0.5",
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                http2=True,
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    @retry(
        wait=wait_exponential(multiplier=60, min=60, max=600),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(RateLimitedException),
    )
    async def fetch_html(self, url: str) -> str:
        async with self.semaphore:
            client = await self._ensure_client()
            logger.info("fbref_fetch_start", url=url)

            response = await client.get(url)

            if response.status_code == 429:
                logger.warning("fbref_rate_limit_429", url=url)
                raise RateLimitedException(f"429 from {url}")

            response.raise_for_status()
            html = response.text

        await asyncio.sleep(self.cooldown)
        return html

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.close()
            self._client = None
