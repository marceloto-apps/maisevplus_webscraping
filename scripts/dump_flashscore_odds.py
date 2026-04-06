import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from camoufox.async_api import AsyncCamoufox

async def main():
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        # Url of a single odds match
        url = "https://www.flashscore.com/match/IsSHKEbU/#/odds-comparison/1x2-odds/full-time"
        print(f"Navigating to {url}")
        try:
            await page.goto(url, timeout=60000, wait_until="commit")
        except Exception as e:
            print(f"Goto timeout or error, trying to continue anyway: {e}")
        
        print("Waiting 10s for JavaScript to inject odds...")
        await page.wait_for_timeout(10000) # delay to let odds load
        
        html = await page.content()
        with open("flashscore_odds_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("HTML saved to flashscore_odds_dump.html")

if __name__ == "__main__":
    asyncio.run(main())
