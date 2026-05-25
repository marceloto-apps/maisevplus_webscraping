import asyncio
import sys
import os
from datetime import date
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

NEW_LEAGUES = [
    {"code": "CHI_LDP", "name": "Primera División", "country": "Chile", "path": "football/chile/liga-de-primera"},
    {"code": "USA_MLS", "name": "MLS", "country": "USA", "path": "football/usa/mls"},
    {"code": "BRA_SB", "name": "Série B", "country": "Brazil", "path": "football/brazil/serie-b"},
    {"code": "NOR_ELI", "name": "Eliteserien", "country": "Norway", "path": "football/norway/eliteserien"},
    {"code": "JPN_J1", "name": "J1 League", "country": "Japan", "path": "football/japan/j1-league"},
]

async def main():
    load_dotenv()
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Cadastrar Ligas Novas
        for l in NEW_LEAGUES:
            league_id = await conn.fetchval("""
                INSERT INTO leagues (code, name, country, flashscore_path, primary_source, season_format, tier, is_active)
                VALUES ($1, $2, $3, $4, 'flashscore', 'feb_dec', 1, TRUE)
                ON CONFLICT (code) DO UPDATE SET
                    flashscore_path = EXCLUDED.flashscore_path,
                    primary_source = EXCLUDED.primary_source
                RETURNING league_id;
            """, l["code"], l["name"], l["country"], l["path"])
            print(f"Liga {l['code']} cadastrada/atualizada (ID: {league_id})")

            # Cadastrar temporadas (2022 a 2026)
            for year in [2022, 2023, 2024, 2025, 2026]:
                await conn.execute("""
                    INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, is_current)
                    VALUES ($1, $2, $3, $4, 0, $5)
                    ON CONFLICT (league_id, label) DO UPDATE SET is_current = EXCLUDED.is_current
                """, league_id, str(year), date(year, 2, 1), date(year, 12, 31), (year == 2026))
            print(f"   Temporadas 2022-2026 cadastradas/atualizadas para {l['code']}.")

        # 2. Registrar temporadas faltantes da Argentina (ARG_LP)
        arg_id = await conn.fetchval("SELECT league_id FROM leagues WHERE code = 'ARG_LP'")
        if arg_id:
            for year in [2022, 2023, 2024, 2025]:
                await conn.execute("""
                    INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, is_current)
                    VALUES ($1, $2, $3, $4, 0, FALSE)
                    ON CONFLICT (league_id, label) DO UPDATE SET is_current = EXCLUDED.is_current
                """, arg_id, str(year), date(year, 2, 1), date(year, 12, 31))
            print(f"   Temporadas 2022-2025 cadastradas/atualizadas para ARG_LP.")
            
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
