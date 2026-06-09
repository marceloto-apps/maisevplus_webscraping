import asyncio
import sys
import os
from datetime import date
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

NEW_LEAGUES = [
    {"code": "IRL_D1", "name": "Division 1", "country": "Ireland", "path": "football/ireland/division-1", "season_format": "feb_dec"},
    {"code": "ARG_PN", "name": "Primera Nacional", "country": "Argentina", "path": "football/argentina/primera-nacional", "season_format": "feb_dec"},
    {"code": "AUS_AL", "name": "A-League", "country": "Australia", "path": "football/australia/a-league", "season_format": "aug_may"},
    {"code": "AUT_L2", "name": "2. Liga", "country": "Austria", "path": "football/austria/2-liga", "season_format": "aug_may"},
    {"code": "BEL_CPL", "name": "Challenger Pro League", "country": "Belgium", "path": "football/belgium/challenger-pro-league", "season_format": "aug_may"},
    {"code": "NED_ED2", "name": "Eerste Divisie", "country": "Netherlands", "path": "football/netherlands/eerste-divisie", "season_format": "aug_may"},
    {"code": "POR_L2", "name": "Liga Portugal 2", "country": "Portugal", "path": "football/portugal/liga-portugal-2", "season_format": "aug_may"},
    {"code": "SWI_CL", "name": "Challenge League", "country": "Switzerland", "path": "football/switzerland/challenge-league", "season_format": "aug_may"},
    {"code": "SAU_D1", "name": "Division 1", "country": "Saudi Arabia", "path": "football/saudi-arabia/division-1", "season_format": "aug_may"},
    {"code": "BUL_PL", "name": "Parva Liga", "country": "Bulgaria", "path": "football/bulgaria/parva-liga", "season_format": "aug_may"},
    {"code": "CRO_HNL", "name": "HNL", "country": "Croatia", "path": "football/croatia/hnl", "season_format": "aug_may"},
    {"code": "DEN_SL", "name": "Superliga", "country": "Denmark", "path": "football/denmark/superliga", "season_format": "aug_may"},
    {"code": "EGY_PL", "name": "Premier League", "country": "Egypt", "path": "football/egypt/premier-league", "season_format": "aug_may"},
    {"code": "HUN_N1", "name": "NB I", "country": "Hungary", "path": "football/hungary/otp-bank-liga", "season_format": "aug_may"},
    {"code": "ISL_BDK", "name": "Besta deild karla", "country": "Iceland", "path": "football/iceland/besta-deild-karla", "season_format": "feb_dec"},
    {"code": "ISR_LHA", "name": "Ligat ha'Al", "country": "Israel", "path": "football/israel/ligat-ha-al", "season_format": "aug_may"},
    {"code": "POL_EK", "name": "Ekstraklasa", "country": "Poland", "path": "football/poland/ekstraklasa", "season_format": "aug_may"},
    {"code": "ROM_SL", "name": "Superliga", "country": "Romania", "path": "football/romania/superliga", "season_format": "aug_may"},
    {"code": "SRB_SL", "name": "Super Liga", "country": "Serbia", "path": "football/serbia/super-liga", "season_format": "aug_may"},
]

async def main():
    load_dotenv()
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("=== REGISTERING NEW FLASHSCORE BACKFILL LEAGUES ===")
        for l in NEW_LEAGUES:
            # Cadastra ou atualiza a liga
            league_id = await conn.fetchval("""
                INSERT INTO leagues (code, name, country, flashscore_path, primary_source, season_format, tier, is_active)
                VALUES ($1, $2, $3, $4, 'flashscore', $5, 3, TRUE)
                ON CONFLICT (code) DO UPDATE SET
                    flashscore_path = EXCLUDED.flashscore_path,
                    primary_source = EXCLUDED.primary_source,
                    season_format = EXCLUDED.season_format,
                    is_active = TRUE
                RETURNING league_id;
            """, l["code"], l["name"], l["country"], l["path"], l["season_format"])
            print(f"Liga {l['code']} ({l['name']}) registrada/atualizada (ID: {league_id})")

            # Cadastra as temporadas correspondentes
            if l["season_format"] == "feb_dec":
                # Ligas de verão: temporadas anuais 2022 a 2026
                for year in [2022, 2023, 2024, 2025, 2026]:
                    is_current = (year == 2026)
                    await conn.execute("""
                        INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, is_current)
                        VALUES ($1, $2, $3, $4, 0, $5)
                        ON CONFLICT (league_id, label) DO UPDATE SET is_current = EXCLUDED.is_current
                    """, league_id, str(year), date(year, 2, 1), date(year, 12, 31), is_current)
                print(f"   Temporadas 2022-2026 associadas a {l['code']}.")
            else:
                # Ligas de inverno: temporadas formatadas YYYY/YYYY (2021/2022 a 2025/2026)
                seasons_to_register = [
                    (2021, 2022, "2021/2022"),
                    (2022, 2023, "2022/2023"),
                    (2023, 2024, "2023/2024"),
                    (2024, 2025, "2024/2025"),
                    (2025, 2026, "2025/2026")
                ]
                for start_yr, end_yr, label in seasons_to_register:
                    is_current = (label == "2025/2026")
                    await conn.execute("""
                        INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, is_current)
                        VALUES ($1, $2, $3, $4, 0, $5)
                        ON CONFLICT (league_id, label) DO UPDATE SET is_current = EXCLUDED.is_current
                    """, league_id, label, date(start_yr, 8, 1), date(end_yr, 5, 31), is_current)
                print(f"   Temporadas 2021/2022-2025/2026 associadas a {l['code']}.")

    await pool.close()
    print("Todas as 19 novas ligas e suas temporadas foram registradas no DB!")

if __name__ == "__main__":
    asyncio.run(main())
