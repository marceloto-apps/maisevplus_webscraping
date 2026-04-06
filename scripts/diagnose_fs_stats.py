"""
Intercept network requests from Flashscore stats page 
to find the internal API endpoint for statistics data.
"""
import sys, os, asyncio, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from camoufox.async_api import AsyncCamoufox
    
    flashscore_id = "IsSHKEbU"
    stats_url = f"https://www.flashscore.com/match/{flashscore_id}/#/match-summary/match-statistics/0"

    print("=" * 60)
    print("INTERCEPT NETWORK — FLASHSCORE STATS API")
    print("=" * 60)
    
    captured_responses = []
    
    async with AsyncCamoufox(headless=False, os="linux") as browser:
        page = await browser.new_page()
        
        # Interceptar TODAS as respostas de rede
        async def on_response(response):
            url = response.url
            # Filtrar CSS, imagens, fontes
            if any(ext in url for ext in ['.css', '.png', '.jpg', '.svg', '.woff', '.gif', '.ico']):
                return
            try:
                status = response.status
                content_type = response.headers.get('content-type', '')
                body_preview = ""
                if 'json' in content_type or 'text' in content_type or 'javascript' not in content_type:
                    try:
                        body = await response.text()
                        # Check if body contains stats keywords
                        has_xgot = 'xGOT' in body or 'xgot' in body
                        has_crosses = 'Crosses' in body or 'crosses' in body
                        has_xa = 'Expected assists' in body or 'xA)' in body
                        if has_xgot or has_crosses or has_xa:
                            body_preview = f" *** CONTAINS STATS! xGOT={has_xgot} Crosses={has_crosses} xA={has_xa} ***"
                            # Save full body
                            safe_name = url.split('/')[-1][:50].replace('?', '_')
                            with open(f"captured_stats_{safe_name}.txt", "w", encoding="utf-8") as f:
                                f.write(f"URL: {url}\n\n{body}")
                        elif len(body) > 500:
                            body_preview = f" ({len(body)} chars)"
                    except:
                        body_preview = " (binary)"
                
                captured_responses.append({
                    'url': url[:120], 'status': status, 'type': content_type[:30], 'note': body_preview
                })
            except:
                pass
        
        page.on('response', on_response)
        
        print(f"\n[1] Navegando para {stats_url}")
        await page.goto(stats_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(8000)
        
        # Scroll para tentar disparar mais requests
        for _ in range(10):
            await page.mouse.wheel(0, 500)
            await page.wait_for_timeout(500)
        
        await page.wait_for_timeout(3000)
        
        print(f"\n[2] Total de respostas capturadas: {len(captured_responses)}")
        print("\nRespostas relevantes (não-triviais):")
        for r in captured_responses:
            note = r['note']
            if note:  # only show non-empty notes
                print(f"  [{r['status']}] {r['url']}")
                print(f"       type={r['type']} {note}")
        
        print("\n\nTODAS as URLs capturadas:")
        for r in captured_responses:
            print(f"  [{r['status']}] {r['url']}")
        
        await page.close()

if __name__ == "__main__":
    asyncio.run(main())
