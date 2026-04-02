"""
Engine B: Playwright async — para mercados secundários (OU, AH, DC, DNB, BTTS, HT)
Headless browser que clica nas tabs e extrai o HTML renderizado.
"""
import asyncio
import random
from typing import Optional
from contextlib import asynccontextmanager

from .config import BASE_URL, USER_AGENTS, RateLimitConfig, MARKET_TABS

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class BetExplorerBrowserClient:
    """
    Browser client para mercados que precisam de JS rendering.
    
    Workflow por jogo:
    1. Navega para a URL do jogo (1X2 carrega por default)
    2. Para cada mercado secundário: click na tab → wait → extract HTML
    3. Retorna dict {market_key: html_content}
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "playwright não instalado. "
                "Execute: pip install playwright && playwright install chromium"
            )
        self.config = config or RateLimitConfig()
        self._pages_in_session = 0
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    @asynccontextmanager
    async def _get_browser(self):
        """Context manager que gerencia lifecycle do browser."""
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ]
            )
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/Sao_Paulo",
                java_script_enabled=True,
            )
            # Stealth: remove webdriver flag
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            yield browser, context
        finally:
            await browser.close()
            await pw.stop()

    async def extract_match_markets(
        self,
        match_url: str,
        markets: list[str],
    ) -> dict[str, str]:
        results = {}

        async with self._get_browser() as (browser, context):
            page = await context.new_page()

            try:
                # Navega para a página do jogo
                await page.goto(match_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(1.5)
                
                # Aguarda a primeira tabela de odds aparecer na DOM
                try:
                    await page.wait_for_selector("table.table-main, table[id*='sortable']", timeout=10000)
                except Exception:
                    pass

                for market_key in markets:
                    market_config = MARKET_TABS.get(market_key)
                    if not market_config or market_config["engine"] != "playwright":
                        continue

                    tab_selector = market_config.get("tab_selector")
                    if not tab_selector:
                        # Mercados HT com parent_tab: precisa clicar no parent primeiro
                        parent_key = market_config.get("parent_tab")
                        if parent_key:
                            parent_config = MARKET_TABS.get(parent_key, {})
                            parent_selector = parent_config.get("tab_selector")
                            if parent_selector:
                                await self._click_tab(page, parent_selector, parent_key)

                        hash_frag = market_config["hash"]
                        await page.evaluate(f"window.location.hash = '{hash_frag}'")
                        await asyncio.sleep(self.config.browser_wait_after_click)
                    else:
                        await self._click_tab(page, tab_selector, market_key)

                    html = await self._extract_odds_html(page)
                    results[market_key] = html

                    await asyncio.sleep(
                        self.config.browser_tab_delay + random.uniform(0, 1.0)
                    )

            except Exception as e:
                results["_error"] = str(e)
            finally:
                await page.close()

        self._pages_in_session += 1
        return results

    async def _click_tab(self, page: Page, selector: str, market_key: str):
        try:
            selectors = [s.strip() for s in selector.split(",")]
            clicked = False

            for sel in selectors:
                try:
                    element = await page.wait_for_selector(sel, timeout=5000)
                    if element:
                        await element.click()
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                hash_frag = MARKET_TABS.get(market_key, {}).get("hash", "")
                if hash_frag:
                    await page.evaluate(f"window.location.hash = '{hash_frag}'")

            await asyncio.sleep(self.config.browser_wait_after_click)

        except Exception as e:
            print(f"    ⚠️ Falha ao clicar tab {market_key}: {e}")

    async def _extract_odds_html(self, page: Page) -> str:
        try:
            return await page.content()
        except Exception as e:
            return f"<!-- extraction error: {e} -->"
