"""Importar aliases dos dois CSVs preenchidos e inserir na DB"""
import asyncio
import csv
from src.db.pool import get_pool

async def main():
    pool = await get_pool()
    
    # Ler os dois CSVs
    all_aliases = []
    for filepath in ['output/unresolved_aliases_manual.csv', 'output/unresolved_remaining.csv']:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('footystats_name', '').strip()
                canonical = row.get('canonical_name', '').strip()
                if name and canonical:
                    all_aliases.append((name, canonical))
    
    print(f"Total de aliases a importar: {len(all_aliases)}")
    
    async with pool.acquire() as conn:
        ok = 0
        not_found = []
        
        for fs_name, canonical in all_aliases:
            # Buscar team_id pelo nome canônico
            team_id = await conn.fetchval(
                "SELECT team_id FROM teams WHERE LOWER(name_canonical) = LOWER($1)",
                canonical
            )
            if not team_id:
                # Busca parcial
                team_id = await conn.fetchval(
                    "SELECT team_id FROM teams WHERE LOWER(name_canonical) LIKE LOWER($1) LIMIT 1",
                    f"%{canonical}%"
                )
            
            if team_id:
                await conn.execute(
                    "INSERT INTO team_aliases (source, alias_name, team_id) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                    'footystats', fs_name.lower(), team_id
                )
                ok += 1
            else:
                not_found.append((fs_name, canonical))
        
        total = await conn.fetchval("SELECT COUNT(*) FROM team_aliases WHERE source = 'footystats'")
        print(f"\n✅ Inseridos: {ok}")
        print(f"Total aliases footystats na DB: {total}")
        
        if not_found:
            print(f"\n❌ NÃO ENCONTRADOS ({len(not_found)}):")
            for fs, canon in not_found:
                print(f"  {fs} → '{canon}' (não existe na tabela teams)")
    
    await pool.close()

asyncio.run(main())
