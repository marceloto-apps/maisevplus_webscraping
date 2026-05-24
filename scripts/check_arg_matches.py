import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

load_dotenv()

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM matches WHERE league_id = 28")
        print(f"Total de partidas na liga 28 (ARG_LP): {count}")
        
        if count > 0:
            rows = await conn.fetch("""
                SELECT m.match_id, m.flashscore_id, m.status, m.kickoff,
                       th.name_canonical AS home, ta.name_canonical AS away
                FROM matches m
                JOIN teams th ON m.home_team_id = th.team_id
                JOIN teams ta ON m.away_team_id = ta.team_id
                WHERE m.league_id = 28
                ORDER BY m.kickoff DESC
                LIMIT 10
            """)
            print("\nÚltimos 10 jogos inseridos:")
            for r in rows:
                print(f"  {r['kickoff']} | {r['home']} vs {r['away']} | Status: {r['status']} | FS ID: {r['flashscore_id']}")
        else:
            print("\nNenhum jogo inserido para a liga 28.")
            
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
