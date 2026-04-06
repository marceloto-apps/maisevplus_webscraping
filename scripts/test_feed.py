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
        
        # 1. Start at odds page
        odds_url = f"https://www.flashscore.com/match/{flashscore_id}/#/odds-comparison/1x2-odds/full-time"
        print("[1] Navigating to odds page...")
        await page.goto(odds_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # 2. Inject interceptors BEFORE navigating to stats
        print("[2] Injecting fetch/XHR interceptors...")
        await page.evaluate("""
            window._flashscore_stats_feed = null;
            
            // XHR Interceptor
            const originalXHR = window.XMLHttpRequest.prototype.open;
            window.XMLHttpRequest.prototype.open = function(method, url) {
                this.addEventListener('load', function() {
                    if (url && url.includes('df_st_1_')) {
                        window._flashscore_stats_feed = this.responseText;
                    }
                });
                return originalXHR.apply(this, arguments);
            };
            
            // Fetch Interceptor
            const originalFetch = window.fetch;
            window.fetch = async function(...args) {
                const response = await originalFetch.call(window, ...args);
                try {
                    const url = typeof args[0] === 'string' ? args[0] : (args[0] ? args[0].url : '');
                    if (url && url.includes('df_st_1_')) {
                        const clone = response.clone();
                        clone.text().then(text => { window._flashscore_stats_feed = text; }).catch(e => {});
                    }
                } catch(e) {}
                return response;
            };
        """)
        
        # 3. Navigate to match summary, then stats
        print("[3] Navigating to stats page...")
        stats_url = f"https://www.flashscore.com/match/{flashscore_id}/#/match-summary/match-statistics/0"
        await page.goto(stats_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        print(f"[4] Clicking 'Stats' tab...")
        try:
            stats_link = page.locator("a:has-text('Stats'), a:has-text('Statistics')").first
            await stats_link.click()
        except Exception as e:
            print(f"Error clicking: {e}")
            
        print("[5] Waiting for interceptor to catch data...")
        # Poll for window._flashscore_stats_feed
        intercepted_data = None
        for i in range(10):
            await page.wait_for_timeout(1000)
            data = await page.evaluate("window._flashscore_stats_feed")
            if data:
                intercepted_data = data
                break
                
        print(f"\nResult: {'SUCCESS' if intercepted_data else 'FAILED'}")
        if intercepted_data:
            has_xgot = 'xGOT' in intercepted_data
            print(f"Chars captured: {len(intercepted_data)}")
            print(f"Contains xGOT: {has_xgot}")
        
        await page.close()

if __name__ == "__main__":
    asyncio.run(main())
