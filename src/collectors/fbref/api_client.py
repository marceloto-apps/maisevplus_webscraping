"""
T08 — FBRef API Client
Rate limit defensivo: Semaphore(1) + cooldown 4.0s + backoff exponencial em 429.
"""
import asyncio
import undetected_chromedriver as uc
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
        self.driver = None

    async def _ensure_client(self):
        if self.driver is None:
            self.driver = await asyncio.to_thread(self._init_driver)
        return self.driver

    def _init_driver(self):
        options = uc.ChromeOptions()
        # Usa o headless moderno que tem muito menos fingerprinting
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        return uc.Chrome(options=options, version_main=146)

    @retry(
        wait=wait_exponential(multiplier=60, min=60, max=600),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(RateLimitedException),
    )
    async def fetch_html(self, url: str) -> str:
        async with self.semaphore:
            driver = await self._ensure_client()
            logger.info("fbref_fetch_start", url=url)

            await asyncio.to_thread(driver.get, url)
            html = driver.page_source

            if "Just a moment..." in html or "Attention Required!" in html or "403 Forbidden" in html:
                logger.warning("fbref_rate_limit_429", url=url)
                raise RateLimitedException(f"Cloudflare/429 from {url}")

        await asyncio.sleep(self.cooldown)
        return html

    async def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
