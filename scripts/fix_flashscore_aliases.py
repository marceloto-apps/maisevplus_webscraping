"""
Script rápido para inserir aliases Flashscore abreviados da ENG_PL.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

# (flashscore_name, team_id)
ALIASES = [
    ("West Ham", 490),          # West Ham United
    ("Nottingham", 334),        # Nottingham Forest
    ("Leeds", 275),             # Leeds United
    ("Manchester Utd", 299),    # Manchester United
    ("Wolves", 497),            # Wolverhampton Wanderers
    ("Everton2", 177),          # Everton (quirk do Flashscore)
]

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        for alias, tid in ALIASES:
            await conn.execute(
                "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'flashscore', $2) ON CONFLICT DO NOTHING",
                tid, alias
            )
            canonical = await conn.fetchval("SELECT name_canonical FROM teams WHERE team_id = $1", tid)
            print(f"  ✅ {alias} → {canonical} (team_id={tid})")
    print("\nDone! Agora rode o discovery novamente.")

if __name__ == "__main__":
    asyncio.run(main())
