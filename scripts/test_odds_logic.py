import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from camoufox.async_api import AsyncCamoufox
from bs4 import BeautifulSoup

async def main():
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        f_id = "IsSHKEbU"
        market_config = {"path": "1x2-odds", "period": "full-time"}
        
        # 1. Obter a URL real baseada no slug dos times resolvendo um link
        url = f"https://www.flashscore.com/match/{f_id}/"
        print(f"Resolving: {url}")
        
        await page.goto(url, timeout=30000, wait_until="commit")
        await page.wait_for_timeout(3000)
        
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        
        odds_href = None
        for a in soup.find_all("a"):
            href = str(a.get("href"))
            if "/odds/" in href and f_id in href:
                odds_href = href
                break
                
        if not odds_href:
            print("Não encontrou o link de odds na Home do match!")
            # Tentar compor manual através da page.url
            print(f"Page.url = {page.url}")
            return
            
        base_odds = odds_href.split("?")[0]
        if not base_odds.endswith("/"):
            base_odds += "/"
            
        # 2. Visitar o Link de Odds real
        target_url = f"https://www.flashscore.com{base_odds}{market_config['path']}/{market_config['period']}/?mid={f_id}"
        print(f"Navegando para o mercado real: {target_url}")
        
        await page.goto(target_url, timeout=60000, wait_until="commit")
        await page.wait_for_timeout(5000)
        
        html_odds = await page.content()
        soup_odds = BeautifulSoup(html_odds, "html.parser")
        
        # O Flashscore tipicamente renderiza as linhas em divs com classes terminadas em 'row'
        rows = soup_odds.find_all("div", class_=lambda c: c and ("row" in c.lower() or "participant" in c.lower()))
        print(f"Found {len(rows)} potential rows.")
        
        with open("odds_test_result.txt", "w", encoding="utf-8") as f:
            for row in rows[:5]:
                f.write(row.prettify()[:500] + "\n---\n")
                
        print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
