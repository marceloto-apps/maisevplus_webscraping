import asyncio
import sys
import os
from datetime import date
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

ADDITIONAL_LEAGUES = [
    {"code": "PER_L1", "name": "Liga 1", "country": "Peru", "path": "football/peru/liga-1"},
    {"code": "URU_LAU", "name": "Liga AUF", "country": "Uruguay", "path": "football/uruguay/liga-auf-uruguaia"},
    {"code": "COL_PA", "name": "Primera A", "country": "Colombia", "path": "football/colombia/primera-a"},
    {"code": "PAR_CP", "name": "Copa de Primera", "country": "Paraguay", "path": "football/paraguay/copa-de-primera"},
    {"code": "ECU_LP", "name": "Liga Pro", "country": "Ecuador", "path": "football/ecuador/liga-pro"},
    {"code": "BOL_DP", "name": "División Profesional", "country": "Bolivia", "path": "football/bolivia/divisao-profissional"},
    {"code": "USA_USC", "name": "USL Championship", "country": "USA", "path": "football/usa/usl-championship"},
    {"code": "USA_USL1", "name": "USL League One", "country": "USA", "path": "football/usa/usl-league-one"},
    {"code": "CAN_PL", "name": "Premier League", "country": "Canada", "path": "football/canada/canadian-premier-league"},
    {"code": "SWE_SUP", "name": "Superettan", "country": "Sweden", "path": "football/sweden/superettan"},
    {"code": "NOR_OBOS", "name": "OBOS-ligaen", "country": "Norway", "path": "football/norway/obos-ligaen"},
    {"code": "FIN_YKK", "name": "Ykkösliiga", "country": "Finland", "path": "football/finland/ykkosliiga"},
    {"code": "JPN_J2", "name": "J2 League", "country": "Japan", "path": "football/japan/j2-league"},
    {"code": "KOR_K1", "name": "K League 1", "country": "South Korea", "path": "football/south-korea/k-league-1"},
    {"code": "KOR_K2", "name": "K League 2", "country": "South Korea", "path": "football/south-korea/k-league-2"},
    {"code": "IRL_PD", "name": "Premier Division", "country": "Ireland", "path": "football/ireland/premier-division"},
]

async def main():
    load_dotenv()
    pool = await get_pool()
    async with pool.acquire() as conn:
        for l in ADDITIONAL_LEAGUES:
            # Cadastra/Atualiza a liga
            league_id = await conn.fetchval("""
                INSERT INTO leagues (code, name, country, flashscore_path, primary_source, season_format, tier, is_active)
                VALUES ($1, $2, $3, $4, 'flashscore', 'feb_dec', 3, TRUE)
                ON CONFLICT (code) DO UPDATE SET
                    flashscore_path = EXCLUDED.flashscore_path,
                    primary_source = EXCLUDED.primary_source,
                    is_active = TRUE
                RETURNING league_id;
            """, l["code"], l["name"], l["country"], l["path"])
            print(f"Liga {l['code']} cadastrada/atualizada (ID: {league_id})")

            # Cadastra temporadas (2022 a 2026)
            for year in [2022, 2023, 2024, 2025, 2026]:
                await conn.execute("""
                    INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, is_current)
                    VALUES ($1, $2, $3, $4, 0, $5)
                    ON CONFLICT (league_id, label) DO UPDATE SET is_current = EXCLUDED.is_current
                """, league_id, str(year), date(year, 2, 1), date(year, 12, 31), (year == 2026))
            print(f"   Temporadas 2022-2026 cadastradas/atualizadas para {l['code']}.")

    await pool.close()
    print("Todas as 16 ligas adicionais foram registradas com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
