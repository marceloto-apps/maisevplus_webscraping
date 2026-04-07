"""
Script para corrigir aliases API-Football mapeados incorretamente.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Ceara (api_id=129) → team_id=556
        await conn.execute(
            "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'api_football', $2) ON CONFLICT DO NOTHING",
            556, "Ceara"
        )
        await conn.execute(
            "UPDATE teams SET api_football_id = 129 WHERE team_id = 556 AND (api_football_id IS NULL OR api_football_id != 129)"
        )
        print("✅ Ceara (api_id=129) → team_id=556")

        # 2. Austria Klagenfurt — corrigir de 510 para 536
        # Remove alias errado
        await conn.execute(
            "DELETE FROM team_aliases WHERE source = 'api_football' AND alias_name = 'Austria Klagenfurt' AND team_id = 510"
        )
        # Limpa api_football_id errado do Austria Wien (510)
        await conn.execute(
            "UPDATE teams SET api_football_id = NULL WHERE team_id = 510 AND api_football_id = 1405"
        )
        # Insere correto
        await conn.execute(
            "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'api_football', $2) ON CONFLICT DO NOTHING",
            536, "Austria Klagenfurt"
        )
        await conn.execute(
            "UPDATE teams SET api_football_id = 1405 WHERE team_id = 536 AND (api_football_id IS NULL OR api_football_id != 1405)"
        )
        print("✅ Austria Klagenfurt (api_id=1405) → team_id=536 (corrigido de 510)")

        # 3. Sport Recife — corrigir de Sporting Gijon (423) para o correto
        # Remove alias errado
        await conn.execute(
            "DELETE FROM team_aliases WHERE source = 'api_football' AND alias_name = 'Sport Recife' AND team_id = 423"
        )
        # Limpa api_football_id errado do Sporting Gijon (423)
        await conn.execute(
            "UPDATE teams SET api_football_id = NULL WHERE team_id = 423 AND api_football_id = 123"
        )
        # Busca Sport Recife no banco — team_id=557
        sport_id = 557
        await conn.execute(
            "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'api_football', $2) ON CONFLICT DO NOTHING",
            sport_id, "Sport Recife"
        )
        await conn.execute(
            "UPDATE teams SET api_football_id = 123 WHERE team_id = $1 AND (api_football_id IS NULL OR api_football_id != 123)",
            sport_id
        )
        print(f"✅ Sport Recife (api_id=123) → team_id={sport_id}")

    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(main())
