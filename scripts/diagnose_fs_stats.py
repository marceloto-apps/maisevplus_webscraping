"""
Intercept the df_sui response during normal Flashscore navigation
to see if it contains ALL statistics data (xGOT, Crosses, xA).
"""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from camoufox.async_api import AsyncCamoufox
    
    flashscore_id = "IsSHKEbU"
    
    print("=" * 60)
    print("INTERCEPT df_sui RESPONSE")
    print("=" * 60)
    
    captured_feeds = {}
    
    async with AsyncCamoufox(headless=False, os="linux") as browser:
        page = await browser.new_page()
        
        async def on_response(response):
            url = response.url
            if 'flashscore.ninja' in url and 'feed' in url:
                try:
                    body = await response.text()
                    feed_name = url.split('/')[-1]
                    captured_feeds[feed_name] = body
                    print(f"\n  📡 CAPTURED: {feed_name} ({len(body)} chars)")
                    
                    # Check for our targets
                    for keyword in ['xGOT', 'xgot', 'XGOT', 'Crosses', 'crosses', 'xA)', 'Expected assists', 
                                     'Shots on target', 'Ball possession', 'Expected goals']:
                        if keyword in body:
                            idx = body.index(keyword)
                            context = body[max(0,idx-50):idx+80]
                            print(f"    🎯 Found '{keyword}' at pos {idx}: ...{context}...")
                except Exception as e:
                    pass
        
        page.on('response', on_response)
        
        # Navigate to match page (this triggers df_sui)
        print(f"\n[1] Navegando para página do jogo...")
        await page.goto(f"https://www.flashscore.com/match/{flashscore_id}/", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(5000)
        
        # Navigate to stats tab (might trigger additional feeds)
        print(f"\n[2] Navegando para aba de estatísticas...")
        await page.goto(f"https://www.flashscore.com/match/{flashscore_id}/#/match-summary/match-statistics/0", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(5000)
        
        # Try clicking any "Stats" or "Statistics" tab/link if present
        print(f"\n[3] Tentando clicar na aba 'Statistics'...")
        try:
            stats_link = page.locator("a:has-text('Statistics'), a:has-text('Stats'), button:has-text('Statistics')")
            if await stats_link.count() > 0:
                await stats_link.first.click()
                await page.wait_for_timeout(5000)
                print("    Clicked stats tab!")
        except Exception as e:
            print(f"    No stats tab found: {e}")
        
        await page.wait_for_timeout(3000)
        
        print(f"\n\n{'='*60}")
        print(f"RESUMO - FEEDS CAPTURADOS: {len(captured_feeds)}")
        print(f"{'='*60}")
        
        for name, body in captured_feeds.items():
            has_stats = any(kw in body for kw in ['xGOT', 'Crosses', 'xA)', 'Expected goals'])
            flag = " *** HAS STATS ***" if has_stats else ""
            print(f"\n📄 {name} ({len(body)} chars){flag}")
            print(f"   FULL CONTENT:")
            print(body[:3000])
            if len(body) > 3000:
                print(f"   ... (truncated, {len(body) - 3000} more chars)")
        
        await page.close()

if __name__ == "__main__":
    asyncio.run(main())
