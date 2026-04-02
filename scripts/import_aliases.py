import argparse
import asyncio
import csv
from src.db.pool import get_pool
from src.db.logger import get_logger

logger = get_logger(__name__)

async def import_csv(file_path: str):
    pool = await get_pool()
    added_teams = 0
    added_aliases = 0
    skipped = 0
    
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        async with pool.acquire() as conn:
            for row in reader:
                fd_name = row.get("football_data_name", "").strip()
                canonical = row.get("canonical_name_bet365", "").strip()
                country = row.get("country", "").strip()
                
                if not fd_name or not canonical:
                    continue
                    
                # 1. Recupera ou cria time
                team_id = await conn.fetchval(
                    "SELECT team_id FROM teams WHERE name_canonical = $1 AND country = $2",
                    canonical, country
                )
                
                if not team_id:
                    team_id = await conn.fetchval(
                        "INSERT INTO teams (name_canonical, country) VALUES ($1, $2) RETURNING team_id",
                        canonical, country
                    )
                    added_teams += 1
                
                # 2. Registra o Alias
                try:
                    await conn.execute(
                        "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, $2, $3)",
                        team_id, "football_data", fd_name
                    )
                    added_aliases += 1
                except Exception as e:
                    # Ignorable: duplicate constraint
                    skipped += 1
                    
                # 3. Marca na unknown_aliases (caso estivesse rastreado de antes)
                await conn.execute(
                    "UPDATE unknown_aliases SET resolved = TRUE WHERE source = 'football_data' AND raw_name = $1",
                    fd_name
                )
                
    print(f"Importação concluída: {file_path}")
    print(f"[*] Times (Novos):   {added_teams}")
    print(f"[*] Aliases (Novos): {added_aliases}")
    print(f"[*] Duplicados:      {skipped}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, required=True, help="Path to csv file")
    args = parser.parse_args()
    asyncio.run(import_csv(args.file))
