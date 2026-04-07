"""
Test reliable feed interception by clicking the stats tab from the match summary page,
and using page.route to strip compression, avoiding decoding errors.
"""
import sys, os, asyncio

async def main():
    from camoufox.async_api import AsyncCamoufox
    
    flashscore_id = "IsSHKEbU"
    
    print("=" * 60)
    print("TESTING RELIABLE FEED INTERCEPTION")
    print("=" * 60)
    
    async with AsyncCamoufox(headless=False, os="linux") as browser:
        page = await browser.new_page()
        
        stats_feed_data = None
        
        async def handle_route(route):
            # Remove compression header to receive plain text directly
            headers = {k: v for k, v in route.request.headers.items() if k.lower() != 'accept-encoding'}
            try:
                response = await route.fetch(headers=headers)
                body_bytes = await response.body()
                text_data = body_bytes.decode('utf-8', errors='ignore')
                nonlocal stats_feed_data
                stats_feed_data = text_data
                print(f"  📡 [ROUTE] df_st_1_ captured: {len(text_data)} chars")
                await route.fulfill(response=response)
            except Exception as e:
                print(f"Route error: {e}")
                await route.continue_()

        # Intercept df_st_1 feed
        await page.route("**/df_st_1_*", handle_route)
        
        # 1. To trigger the feed reliably, we start at the main Match page
        match_url = f"https://www.flashscore.com/match/{flashscore_id}/#/match-summary/match-summary"
        print("[1] Navigating to Match Summary page...")
        await page.goto(match_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # 2. Click the Statistics sub-tab using the specific href
        print("[2] Clicking 'Statistics' tab using locator...")
        try:
            stats_tab = page.locator('a[href*="match-statistics"]')
            if await stats_tab.count() > 0:
                await stats_tab.first.click()
                print("    Clicked specific sub-tab!")
            else:
                print("    Specific sub-tab not found. Trying text locator...")
                stats_tab = page.locator("a:has-text('Stats'), a:has-text('Statistics')").first
                await stats_tab.click()
                print("    Clicked text locator!")
        except Exception as e:
            print(f"    Click error: {e}")
            
        print("[3] Waiting 8s for the feed...")
        for _ in range(8):
            await page.wait_for_timeout(1000)
            if stats_feed_data:
                break
        
        print(f"\nResult: {'SUCCESS' if stats_feed_data else 'FAILED'}")
        if stats_feed_data:
            has_xgot = 'xGOT' in stats_feed_data
            print(f"Chars captured: {len(stats_feed_data)}")
            print(f"Contains xGOT: {has_xgot}")
        
        await page.close()

if __name__ == "__main__":
    asyncio.run(main())
