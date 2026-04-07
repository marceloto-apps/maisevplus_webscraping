"""
Script rápido para resolver aliases pendentes do API-Football.
Busca pelo api_football_id na tabela teams e insere o alias.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

# (api_football_name, api_football_team_id)
ALIASES_TO_RESOLVE = [
    ("Fortaleza EC", 154),
    ("Juventude", 152),
    ("Ceara", 129),
    ("Sport Recife", 123),
    ("Austria Klagenfurt", 1405),
]

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        for alias_name, api_id in ALIASES_TO_RESOLVE:
            # Tenta achar pelo api_football_id
            team_id = await conn.fetchval(
                "SELECT team_id FROM teams WHERE api_football_id = $1", api_id
            )
            
            if not team_id:
                # Busca fuzzy pelo name_canonical
                row = await conn.fetchrow(
                    "SELECT team_id, name_canonical FROM teams WHERE LOWER(name_canonical) LIKE $1 LIMIT 1",
                    f"%{alias_name.split()[0].lower()}%"
                )
                if row:
                    team_id = row["team_id"]
                    print(f"  🔍 {alias_name} → matched by name: {row['name_canonical']} (id={team_id})")
                    # Salva api_football_id no time
                    await conn.execute(
                        "UPDATE teams SET api_football_id = $1 WHERE team_id = $2 AND api_football_id IS NULL",
                        api_id, team_id
                    )

            if not team_id:
                print(f"  ❌ {alias_name} (api_id={api_id}) — NÃO encontrado no banco!")
                continue

            # Insere alias
            await conn.execute(
                "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'api_football', $2) ON CONFLICT DO NOTHING",
                team_id, alias_name
            )
            
            # Mostra nome canônico
            canonical = await conn.fetchval("SELECT name_canonical FROM teams WHERE team_id = $1", team_id)
            print(f"  ✅ {alias_name} (api_id={api_id}) → {canonical} (team_id={team_id})")

    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(main())
