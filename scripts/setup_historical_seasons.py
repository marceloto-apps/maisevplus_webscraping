import asyncio
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

async def register_seasons(league_code: str, years: list):
    pool = await get_pool()
    async with pool.acquire() as conn:
        league = await conn.fetchrow("SELECT league_id, name FROM leagues WHERE code = $1", league_code)
        if not league:
            print(f"❌ Liga {league_code} não encontrada.")
            return

        league_id = league["league_id"]
        print(f"🏆 Cadastrando temporadas para {league['name']} (ID: {league_id})...")

        for year in years:
            label = str(year)
            # Define o intervalo feb_dec padrão para ligas sul-americanas
            start_date = f"{year}-02-01"
            end_date = f"{year}-12-31"

            season_id = await conn.fetchval("""
                INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, is_current)
                VALUES ($1, $2, $3, $4, 0, FALSE)
                ON CONFLICT (league_id, label) DO UPDATE SET
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date
                RETURNING season_id;
            """, league_id, label, start_date, end_date)
            print(f"   📅 Temporada '{label}' cadastrada/atualizada. ID: {season_id}")
            
    await pool.close()

if __name__ == "__main__":
    # Temporadas históricas solicitadas para Argentina (2022, 2023, 2024, 2025)
    asyncio.run(register_seasons("ARG_LP", [2022, 2023, 2024, 2025]))
