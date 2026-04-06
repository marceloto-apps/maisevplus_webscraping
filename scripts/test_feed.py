"""
Test intercepting via in-page JavaScript to bypass Playwright networking errors.
"""
import sys, os, asyncio

async def main():
    from camoufox.async_api import AsyncCamoufox
    
    flashscore_id = "IsSHKEbU"
    
    print("=" * 60)
    print("TESTING IN-PAGE JS INTERCEPTION")
    print("=" * 60)
    
    async with AsyncCamoufox(headless=False, os="linux") as browser:
        page = await browser.new_page()
        
        stats_feed_data = None
        
        async def intercept_stats_feed(route):
            nonlocal stats_feed_data
            try:
                # Strip compression to avoid decoding errors in headless mode
                headers = {k: v for k, v in route.request.headers.items() if k.lower() != 'accept-encoding'}
                response = await route.fetch(headers=headers)
                stats_feed_data = await response.text()
                print(f"  📡 [ROUTE HIT] df_st_1 capturado via route: {len(stats_feed_data)} chars")
                await route.fulfill(response=response)
            except Exception as e:
                print(f"  ❌ Route error: {e}")
                await route.continue_()
                
        # Intercept df_st_1 feed
        await page.route("**/df_st_1_*", intercept_stats_feed)
        
        # 1. Start at odds page
        odds_url = f"https://www.flashscore.com/match/{flashscore_id}/#/odds-comparison/1x2-odds/full-time"
        print("[1] Navigating to odds page...")
        await page.goto(odds_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # 2. Change hash to trigger stats feed (like in odds_collector)
        print("[2] Changing hash to match-statistics...")
        await page.evaluate('window.location.hash = "#/match-summary/match-statistics/0"')
        
        print("[3] Waiting 10s for the route to trigger...")
        for i in range(10):
            await page.wait_for_timeout(1000)
            if stats_feed_data:
                break
        
        if not stats_feed_data:
            # Fallback: maybe the page needs a hard refresh or click
            print("[4] Not triggered by hash. Trying a full navigation...")
            stats_url = f"https://www.flashscore.com/match/{flashscore_id}/#/match-summary/match-statistics/0"
            await page.goto(stats_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            
            print("[5] Trying to click 'Stats' tab...")
            try:
                stats_link = page.locator("a:has-text('Stats'), a:has-text('Statistics')").first
                await stats_link.click()
                await page.wait_for_timeout(5000)
            except Exception as e:
                print(f"    Click error: {e}")
        
        print(f"\nResult: {'SUCCESS' if stats_feed_data else 'FAILED'}")
        if stats_feed_data:
            has_xgot = 'xGOT' in stats_feed_data
            print(f"Chars captured: {len(stats_feed_data)}")
            print(f"Contains xGOT: {has_xgot}")
        
        await page.close()

if __name__ == "__main__":
    asyncio.run(main())
