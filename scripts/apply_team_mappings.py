import asyncio
import os
import sys
import csv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

async def merge_team(conn, name_pattern: str, keep_id: int):
    """
    Atualiza todas as referencias de times duplicados para o keep_id e deleta os duplicados.
    """
    dupes = await conn.fetch("SELECT team_id, name_canonical FROM teams WHERE name_canonical ILIKE $1 AND team_id != $2", name_pattern, keep_id)
    if not dupes:
        print(f"Nenhuma duplicata encontada para {name_pattern}.")
        return

    for d in dupes:
        bad_id = d['team_id']
        name = d['name_canonical']
        print(f"Mesclando duplicata: '{name}' (ID {bad_id}) -> Manter ID {keep_id}")
        
        # Mapeamento do alias se nao tiver conflito
        # Atualiza FKs
        await conn.execute("UPDATE matches SET home_team_id = $1 WHERE home_team_id = $2", keep_id, bad_id)
        await conn.execute("UPDATE matches SET away_team_id = $1 WHERE away_team_id = $2", keep_id, bad_id)
        await conn.execute("UPDATE lineups SET team_id = $1 WHERE team_id = $2", keep_id, bad_id)
        await conn.execute("UPDATE unknown_aliases SET resolved_team_id = $1 WHERE resolved_team_id = $2", keep_id, bad_id)
        
        # Team aliases podem gerar unique constraint error dependendo. Ignoramos conflitos transferindo de update
        # ou se o alias conflitante existir, apagamos o alias do ruim
        await conn.execute("""
            INSERT INTO team_aliases (team_id, source, alias_name)
            SELECT $1, source, alias_name FROM team_aliases WHERE team_id = $2
            ON CONFLICT (source, alias_name) DO NOTHING
        """, keep_id, bad_id)
        await conn.execute("DELETE FROM team_aliases WHERE team_id = $1", bad_id)
        
        # Apagar Time antigo
        await conn.execute("DELETE FROM teams WHERE team_id = $1", bad_id)
        print(f" ✓ '{name}'(ID {bad_id}) removido.")

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("--- Fase 1: Deduplicação de Times ---")
        await merge_team(conn, '%Flamengo%', 516)
        await merge_team(conn, '%Atlético GO%', 563)
        await merge_team(conn, '%Atletico GO%', 563)
        
        print("\n--- Fase 2: Aplicando Mapeamento API-Football ---")
        csv_path = "api_football_teams_mapping.csv"
        updated = 0
        
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                af_id = int(row['api_football_id'])
                af_name = row['api_football_name']
                db_id_str = row['db_team_id']
                
                if db_id_str.strip():
                    db_id = int(db_id_str)
                    await conn.execute(
                        "UPDATE teams SET api_football_id = $1, api_football_name = $2 WHERE team_id = $3",
                        af_id, af_name, db_id
                    )
                    # Aproveita pra colocar alias caso necessario
                    await conn.execute("""
                        INSERT INTO team_aliases (team_id, source, alias_name)
                        VALUES ($1, 'api_football', $2)
                        ON CONFLICT DO NOTHING
                    """, db_id, af_name)
                    
                    updated += 1
                    
        print(f"✓ Mapeamento aplicado a {updated} times.")

if __name__ == "__main__":
    asyncio.run(main())
