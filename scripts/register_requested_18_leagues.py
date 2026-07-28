"""Script para cadastrar e ativar as 18 novas ligas solicitadas para a rotina de backfill e retrofit.
"""
import asyncio
import os
import sys
from datetime import date
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

REQUESTED_LEAGUES = [
    {"code": "GER_3L",  "name": "3. Liga",             "country": "Germany",              "path": "football/germany/3-liga",             "season_format": "aug_may"},
    {"code": "SAU_SPL", "name": "Saudi Pro League",    "country": "Saudi Arabia",         "path": "football/saudi-arabia/saudi-pro-league", "season_format": "aug_may"},
    {"code": "ARG_TF",  "name": "Torneo Federal",      "country": "Argentina",            "path": "football/argentina/torneo-federal",    "season_format": "feb_dec"},
    {"code": "BHR_PL",  "name": "Premier League",      "country": "Bahrain",              "path": "football/bahrain/premier-league",     "season_format": "aug_may"},
    {"code": "BLR_VL",  "name": "Vysshaya Liga",       "country": "Belarus",              "path": "football/belarus/vysshaya-liga",       "season_format": "feb_dec"},
    {"code": "BRA_SC",  "name": "Série C",             "country": "Brazil",               "path": "football/brazil/serie-c",             "season_format": "feb_dec"},
    {"code": "CHI_LDA", "name": "Liga de Ascenso",     "country": "Chile",                "path": "football/chile/liga-de-ascenso",      "season_format": "feb_dec"},
    {"code": "CHN_L1",  "name": "Jia League",          "country": "China",                "path": "football/china/jia-league",           "season_format": "feb_dec"},
    {"code": "CRO_PNL", "name": "Prva NL",             "country": "Croatia",              "path": "football/croatia/prva-nl",             "season_format": "aug_may"},
    {"code": "DEN_D1",  "name": "1st Division",        "country": "Denmark",              "path": "football/denmark/1st-division",       "season_format": "aug_may"},
    {"code": "FIN_YKK2","name": "Ykkönen",             "country": "Finland",              "path": "football/finland/ykkonen",            "season_format": "feb_dec"},
    {"code": "FRA_NAT", "name": "National",            "country": "France",               "path": "football/france/national",            "season_format": "aug_may"},
    {"code": "ISR_LL",  "name": "Leumit League",       "country": "Israel",               "path": "football/israel/leumit-league",       "season_format": "aug_may"},
    {"code": "ITA_SCA", "name": "Serie C - Group A",   "country": "Italy",                "path": "football/italy/serie-c-group-a",      "season_format": "aug_may"},
    {"code": "ITA_SCB", "name": "Serie C - Group B",   "country": "Italy",                "path": "football/italy/serie-c-group-b",      "season_format": "aug_may"},
    {"code": "ITA_SCC", "name": "Serie C - Group C",   "country": "Italy",                "path": "football/italy/serie-c-group-c",      "season_format": "aug_may"},
    {"code": "POL_D1",  "name": "Division 1",          "country": "Poland",               "path": "football/poland/division-1",          "season_format": "aug_may"},
    {"code": "THA_TL1", "name": "Thai League 1",       "country": "Thailand",             "path": "football/thailand/thai-league-1",     "season_format": "aug_may"},
]

async def main():
    load_dotenv()
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("=== CADASTRANDO AS 18 NOVAS LIGAS PARA BACKFILL E RETROFIT ===")
        registered_count = 0
        for l in REQUESTED_LEAGUES:
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
            print(f"[OK] Liga {l['code']} ({l['name']}) registrada/ativa (ID: {league_id})")

            # Insert seasons
            if l["season_format"] == "feb_dec":
                for year in [2022, 2023, 2024, 2025, 2026]:
                    is_current = (year == 2026)
                    await conn.execute("""
                        INSERT INTO public.seasons (league_id, label, start_date, end_date, footystats_season_id, is_current)
                        VALUES ($1, $2, $3, $4, 0, $5)
                        ON CONFLICT (league_id, label) DO UPDATE SET is_current = EXCLUDED.is_current
                    """, league_id, str(year), date(year, 2, 1), date(year, 12, 31), is_current)
            else:
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

            # Adicionar à fila de retrofit
            await conn.execute("""
                INSERT INTO retrofit_queue (league_id, priority, status, total_matches, processed_matches, success_matches, attempts)
                VALUES ($1, 999, 'pending', 0, 0, 0, 0)
                ON CONFLICT (league_id) DO UPDATE SET
                    status = CASE WHEN retrofit_queue.status = 'completed' THEN 'pending' ELSE retrofit_queue.status END
            """, league_id)
            registered_count += 1

    await pool.close()
    print(f"\n[SUCESSO] Todas as {registered_count} ligas foram registradas e inseridas no banco de dados!")

if __name__ == "__main__":
    asyncio.run(main())
