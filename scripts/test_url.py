import asyncio
import os
import sys

from camoufox.async_api import AsyncCamoufox

async def main():
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        url = "https://www.flashscore.com/match/IsSHKEbU/"
        print(f"Navigating to {url}")
        try:
            await page.goto(url, timeout=30000, wait_until="commit")
            await page.wait_for_timeout(3000)
            print("RESOLVED URL IS:")
            print(page.url)
        except Exception as e:
            print(f"Goto timeout or error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
