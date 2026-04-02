"""
Engine A: httpx async — para listagem de jogos + 1X2 FT
Leve, rápido, sem dependência de browser.
"""
import asyncio
import random
import time
from typing import Optional

import httpx

from .config import BASE_URL, USER_AGENTS, RateLimitConfig

class BetExplorerHttpClient:
    """Cliente HTTP async com rate limiting e retry."""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._agent_idx = 0
        self._request_count = 0
        self._last_request_time = 0.0
        self._minute_window_start = 0.0
        self._minute_request_count = 0

    def _get_headers(self) -> dict:
        agent = USER_AGENTS[self._agent_idx % len(USER_AGENTS)]
        self._agent_idx += 1
        return {
            "User-Agent": agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": f"{BASE_URL}/football/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _rate_limit(self):
        """Aplica rate limiting: delay entre requests + limite por minuto."""
        now = time.monotonic()

        # Reset minute counter
        if now - self._minute_window_start > 60:
            self._minute_window_start = now
            self._minute_request_count = 0

        # Limite por minuto
        if self._minute_request_count >= self.config.http_max_per_minute:
            wait = 60 - (now - self._minute_window_start)
            if wait > 0:
                await asyncio.sleep(wait)
            self._minute_window_start = time.monotonic()
            self._minute_request_count = 0

        # Delay entre requests
        elapsed = now - self._last_request_time
        delay = self.config.http_delay_base + random.uniform(0, self.config.http_delay_jitter)
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)

        self._last_request_time = time.monotonic()
        self._minute_request_count += 1
        self._request_count += 1

    async def get(
        self,
        url: str,
        client: httpx.AsyncClient,
        retry_count: int = 0,
    ) -> tuple[int, str]:
        """
        GET com rate limiting e retry automático em 429.
        Retorna (status_code, html_body).
        """
        await self._rate_limit()

        try:
            resp = await client.get(
                url,
                headers=self._get_headers(),
                follow_redirects=True,
                timeout=30.0,
            )

            # Retry on 429 (Too Many Requests)
            if resp.status_code == 429:
                retries = self.config.http_retry_on_429
                if retry_count < len(retries):
                    wait = retries[retry_count]
                    print(f"    ⏳ 429 em {url} — retry em {wait}s (tentativa {retry_count + 1})")
                    await asyncio.sleep(wait)
                    return await self.get(url, client, retry_count + 1)

            return resp.status_code, resp.text

        except httpx.TimeoutException:
            return 408, ""
        except Exception as e:
            return 0, str(e)

    @property
    def request_count(self) -> int:
        return self._request_count
