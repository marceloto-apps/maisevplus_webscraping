"""
Fetch Flashscore data feeds directly from browser context.
Try different endpoints to find statistics data.
"""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from camoufox.async_api import AsyncCamoufox
    
    flashscore_id = "IsSHKEbU"
    base_feed = "https://global.flashscore.ninja/2/x/feed"
    
    # Endpoints a tentar para stats
    endpoints = [
        f"{base_feed}/df_sui_1_{flashscore_id}",          # summary info (já confirmado 4430 chars)
        f"{base_feed}/df_st_1_{flashscore_id}",            # statistics
        f"{base_feed}/df_sta_1_{flashscore_id}",           # statistics alt
        f"{base_feed}/df_ste_1_{flashscore_id}",           # statistics extended
        f"{base_feed}/df_su_1_{flashscore_id}",            # summary
        f"{base_feed}/df_stt_1_{flashscore_id}",           # stats total
        f"{base_feed}/df_stm_1_{flashscore_id}",           # stats match
    ]
    
    print("=" * 60)
    print("FETCH FLASHSCORE FEEDS — PROCURANDO STATS API")
    print("=" * 60)
    
    async with AsyncCamoufox(headless=False, os="linux") as browser:
        # Primeiro navegar ao site para pegar cookies/session
        page = await browser.new_page()
        await page.goto(f"https://www.flashscore.com/match/{flashscore_id}/", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)
        
        for url in endpoints:
            print(f"\n[FETCH] {url}")
            try:
                response = await page.evaluate(f"""
                    async () => {{
                        try {{
                            const resp = await fetch("{url}");
                            const text = await resp.text();
                            return {{ status: resp.status, length: text.length, body: text.substring(0, 2000) }};
                        }} catch(e) {{
                            return {{ status: -1, length: 0, body: e.message }};
                        }}
                    }}
                """)
                status = response['status']
                length = response['length']
                body = response['body']
                
                has_xgot = 'xGOT' in body or 'xgot' in body or 'XGOT' in body
                has_crosses = 'Crosses' in body or 'crosses' in body or 'CROSSES' in body
                has_xa = 'xA)' in body or 'Expected assists' in body
                
                flag = ""
                if has_xgot or has_crosses or has_xa:
                    flag = f" *** HIT! xGOT={has_xgot} Crosses={has_crosses} xA={has_xa} ***"
                
                print(f"  Status={status} | Size={length} chars{flag}")
                if length > 0 and length < 10000:
                    print(f"  BODY (first 2000 chars):\n{body}")
                elif length >= 10000:
                    print(f"  BODY (first 2000 chars):\n{body}")
                    
            except Exception as e:
                print(f"  ERROR: {e}")
        
        await page.close()

if __name__ == "__main__":
    asyncio.run(main())
