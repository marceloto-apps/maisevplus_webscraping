import asyncio
import sys
import os
from datetime import date
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

NEW_LEAGUES = [
    {"code": "ZAF_PL", "name": "Premiership", "country": "South Africa", "path": "football/south-africa/premier-league", "season_format": "aug_may"},
    {"code": "BIH_PL", "name": "wwin Liga BiH", "country": "Bosnia & Herzegovina", "path": "football/bosnia-and-herzegovina/wwin-liga-bih", "season_format": "aug_may"},
    {"code": "QAT_PL", "name": "QSL", "country": "Qatar", "path": "football/qatar/qsl", "season_format": "aug_may"},
    {"code": "CRC_PD", "name": "Primera Division", "country": "Costa Rica", "path": "football/costa-rica/primera-division", "season_format": "aug_may"},
    {"code": "SVK_NL", "name": "Nike Liga", "country": "Slovakia", "path": "football/slovakia/nike-liga", "season_format": "aug_may"},
    {"code": "EST_ML", "name": "Meistriliiga", "country": "Estonia", "path": "football/estonia/meistriliiga", "season_format": "feb_dec"},
    {"code": "SVN_PL", "name": "Prva Liga", "country": "Slovenia", "path": "football/slovenia/prva-liga", "season_format": "aug_may"},
    {"code": "GEO_CEL", "name": "Crystalbet Erovnuli Liga", "country": "Georgia", "path": "football/georgia/crystalbet-erovnuli-liga", "season_format": "feb_dec"},
    {"code": "GRE_SL2", "name": "Super League 2", "country": "Greece", "path": "football/greece/super-league-2", "season_format": "aug_may"},
    {"code": "HUN_NB2", "name": "NB II", "country": "Hungary", "path": "football/hungary/mercantil-bank-liga", "season_format": "aug_may"},
    {"code": "FRO_PL", "name": "Premier League", "country": "Faroe Islands", "path": "football/faroe-islands/premier-league", "season_format": "feb_dec"},
    {"code": "IND_ISL", "name": "ISL", "country": "India", "path": "football/india/isl", "season_format": "aug_may"},
    {"code": "IDN_SL", "name": "Liga 1", "country": "Indonesia", "path": "football/indonesia/liga-1", "season_format": "aug_may"},
    {"code": "NIR_PL", "name": "NIFL Premiership", "country": "Northern Ireland", "path": "football/northern-ireland/nifl-premiership", "season_format": "aug_may"},
    {"code": "LVA_VS", "name": "Optibet Virsliga", "country": "Latvia", "path": "football/latvia/optibet-virsliga", "season_format": "feb_dec"},
    {"code": "LTU_TL", "name": "A Lyga", "country": "Lithuania", "path": "football/lithuania/a-lyga", "season_format": "feb_dec"},
    {"code": "MAR_BP", "name": "Botola Pro", "country": "Morocco", "path": "football/morocco/botola-pro", "season_format": "aug_may"},
    {"code": "WAL_CP", "name": "Cymru Premier", "country": "Wales", "path": "football/wales/cymru-premier", "season_format": "aug_may"},
    {"code": "POL_D1", "name": "Division 1", "country": "Poland", "path": "football/poland/division-1", "season_format": "aug_may"},
    {"code": "CZE_CL", "name": "Chance Liga", "country": "Czech Republic", "path": "football/czech-republic/chance-liga", "season_format": "aug_may"},
    {"code": "RUS_PL", "name": "FNL", "country": "Russia", "path": "football/russia/fnl", "season_format": "aug_may"},
    {"code": "TUR_1L", "name": "1. Lig", "country": "Turkey", "path": "football/turkey/1-lig", "season_format": "aug_may"},
    {"code": "UKR_PL", "name": "Premier League", "country": "Ukraine", "path": "football/ukraine/premier-league", "season_format": "aug_may"},
    {"code": "VEN_LF", "name": "Liga FUTVE", "country": "Venezuela", "path": "football/venezuela/liga-futve", "season_format": "feb_dec"},
]

async def main():
    load_dotenv()
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("=== REGISTERING MORE FLASHSCORE BACKFILL LEAGUES ===")
        for l in NEW_LEAGUES:
            # Insert or update league
            league_id = await conn.fetchval("""
                INSERT INTO public.leagues (code, name, country, flashscore_path, primary_source, season_format, tier, is_active)
                VALUES ($1, $2, $3, $4, 'flashscore', $5, 3, TRUE)
                ON CONFLICT (code) DO UPDATE SET
                    flashscore_path = EXCLUDED.flashscore_path,
                    primary_source = EXCLUDED.primary_source,
                    season_format = EXCLUDED.season_format,
                    is_active = TRUE
                RETURNING league_id;
            """, l["code"], l["name"], l["country"], l["path"], l["season_format"])
            print(f"Liga {l['code']} ({l['name']}) registrada/atualizada (ID: {league_id})")

            # Insert seasons
            if l["season_format"] == "feb_dec":
                # Summer format: 2022 to 2026
                for year in [2022, 2023, 2024, 2025, 2026]:
                    is_current = (year == 2026)
                    await conn.execute("""
                        INSERT INTO public.seasons (league_id, label, start_date, end_date, footystats_season_id, is_current)
                        VALUES ($1, $2, $3, $4, 0, $5)
                        ON CONFLICT (league_id, label) DO UPDATE SET is_current = EXCLUDED.is_current
                    """, league_id, str(year), date(year, 2, 1), date(year, 12, 31), is_current)
                print(f"   Temporadas 2022-2026 associadas a {l['code']}.")
            else:
                # Winter format: 2021/2022 to 2025/2026
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
                        INSERT INTO public.seasons (league_id, label, start_date, end_date, footystats_season_id, is_current)
                        VALUES ($1, $2, $3, $4, 0, $5)
                        ON CONFLICT (league_id, label) DO UPDATE SET is_current = EXCLUDED.is_current
                    """, league_id, label, date(start_yr, 8, 1), date(end_yr, 5, 31), is_current)
                print(f"   Temporadas 2021/2022-2025/2026 associadas a {l['code']}.")

    await pool.close()
    print("Todas as 24 novas ligas foram registradas com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
