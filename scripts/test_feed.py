"""
Testing the exact mechanism to intercept the df_st_1 feed.
"""
import sys, os, asyncio

async def main():
    from camoufox.async_api import AsyncCamoufox
    
    flashscore_id = "IsSHKEbU"
    
    print("=" * 60)
    print("TESTING EXACT FEED INTERCEPTION")
    print("=" * 60)
    
    stats_feed_data = None
    
    async with AsyncCamoufox(headless=False, os="linux") as browser:
        page = await browser.new_page()
        
        async def capture_stats_feed(response):
            nonlocal stats_feed_data
            if f"df_st_1_{flashscore_id}" in response.url:
                try:
                    stats_feed_data = await response.text()
                    print(f"  📡 [SUCCESS] Feed df_st_1 capturado: {len(stats_feed_data)} chars")
                except Exception as e:
                    print(f"  ❌ Error capturing: {e}")
        
        page.on("response", capture_stats_feed)
        
        # SIMULAR O MESMO ESTADO DE odds_collector: 
        # começa na página de odds
        odds_url = f"https://www.flashscore.com/match/{flashscore_id}/#/odds-comparison/1x2-odds/full-time"
        print("[1] Navigating to odds page...")
        await page.goto(odds_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # AGORA, sequencia exata do diagnóstico
        stats_url = f"https://www.flashscore.com/match/{flashscore_id}/#/match-summary/match-statistics/0"
        print("[2] Navigating to stats page directly...")
        await page.goto(stats_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        print(f"[3] Clicking 'Stats' tab...")
        try:
            stats_link = page.locator("a:has-text('Stats'), a:has-text('Statistics')").first
            await stats_link.click()
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"Error clicking: {e}")
            
        print(f"\nResult: {'SUCCESS' if stats_feed_data else 'FAILED'}")
        
        await page.close()

if __name__ == "__main__":
    asyncio.run(main())
