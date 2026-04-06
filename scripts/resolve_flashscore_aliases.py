"""
scripts/resolve_flashscore_aliases.py

Resolve aliases de times do Flashscore para o banco de dados.
  1. Busca nomes não resolvidos nos logs de discovery (via argumento ou todos).
  2. Auto-resolve se fuzzy match >= 90%.
  3. Para scores < 90%, mostra candidatos para resolução interativa.

Uso:
  python scripts/resolve_flashscore_aliases.py
  python scripts/resolve_flashscore_aliases.py --names "Athletico-PR,Bragantino2"
"""

import asyncio
import sys
import os
import argparse
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

AUTO_THRESHOLD = 0.90


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def get_all_db_teams(pool) -> list:
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT team_id, name_canonical FROM teams ORDER BY name_canonical")


async def get_existing_aliases(pool) -> dict:
    """Retorna dict de alias_lower -> team_id para source='flashscore'"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT alias_name, team_id FROM team_aliases WHERE source = 'flashscore'")
    return {row["alias_name"].lower(): row["team_id"] for row in rows}


async def get_unresolved_names(pool) -> list:
    """
    Busca nomes de times usados em partidas do Flashscore que não foram resolvidos.
    Pega da tabela de discovery ou via nomes não presentes em aliases.
    """
    # Abordagem: pegar todos os nomes do Flashscore que não têm alias
    # Como não temos uma tabela de "pending", vamos aceitar nomes via argumento
    return []


async def save_alias(pool, team_id: int, alias_name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'flashscore', $2) ON CONFLICT DO NOTHING",
            team_id, alias_name
        )


async def resolve_name(name: str, all_teams: list, existing_aliases: dict, pool) -> dict:
    """Tenta resolver um nome. Retorna dict com resultado."""
    
    # Já existe alias?
    if name.lower() in existing_aliases:
        return {"name": name, "status": "already_exists", "team_id": existing_aliases[name.lower()]}
    
    # Match exato por name_canonical?
    for t in all_teams:
        if t["name_canonical"].lower() == name.lower():
            await save_alias(pool, t["team_id"], name)
            existing_aliases[name.lower()] = t["team_id"]
            return {"name": name, "status": "exact_match", "team_id": t["team_id"], "canonical": t["name_canonical"]}
    
    # Fuzzy matching
    scored = [(t, similarity(name, t["name_canonical"])) for t in all_teams]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:8]
    best_score = top[0][1] if top else 0
    
    # Auto-resolve se >= 90%
    if best_score >= AUTO_THRESHOLD:
        best = top[0][0]
        await save_alias(pool, best["team_id"], name)
        existing_aliases[name.lower()] = best["team_id"]
        return {
            "name": name, "status": "auto_resolved", 
            "team_id": best["team_id"], "canonical": best["name_canonical"],
            "score": best_score
        }
    
    # Requer interação
    return {"name": name, "status": "needs_input", "candidates": top}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--names", help="Nomes separados por vírgula (ex: 'Athletico-PR,Bragantino2')", default=None)
    args = parser.parse_args()

    pool = await get_pool()
    all_teams = await get_all_db_teams(pool)
    existing_aliases = await get_existing_aliases(pool)

    # Coleta nomes a resolver
    if args.names:
        names = [n.strip() for n in args.names.split(",") if n.strip()]
    else:
        # Busca nomes que existem em team_aliases de outras fontes mas não em flashscore
        # E nomes que sabemos que falharam (hardcoded dos logs recentes)
        async with pool.acquire() as conn:
            # Busca nomes que falharam no discovery via log pattern (se tiver tabela de pending)
            # Fallback: busca times da BRA_SA sem alias flashscore
            rows = await conn.fetch("""
                SELECT DISTINCT t.team_id, t.name_canonical 
                FROM teams t
                JOIN seasons s ON TRUE
                JOIN leagues l ON s.league_id = l.league_id AND l.code = 'BRA_SA'
                WHERE s.is_current = TRUE
                AND NOT EXISTS (
                    SELECT 1 FROM team_aliases ta 
                    WHERE ta.team_id = t.team_id AND ta.source = 'flashscore'
                )
                AND t.team_id IN (
                    SELECT home_team_id FROM matches WHERE league_id = l.league_id
                    UNION
                    SELECT away_team_id FROM matches WHERE league_id = l.league_id
                )
                ORDER BY t.name_canonical
            """)
        if rows:
            print(f"\nEncontrados {len(rows)} times da BRA_SA sem alias Flashscore.")
            print("Esses times têm partidas mas não foram mapeados para o Flashscore.\n")
            # Para cada, mostramos o nome canônico (não o nome do flashscore)
            # O ideal aqui é ter o nome do Flashscore. Vamos usar uma lista conhecida.
        
        # Nomes que sabemos que falharam nos logs
        names = ["Athletico-PR", "Bragantino2"]
        print(f"Usando nomes conhecidos dos logs de discovery: {names}")

    print("\n" + "=" * 60)
    print("  RESOLUTOR DE ALIASES — FLASHSCORE")
    print("=" * 60)
    print(f"  Times no DB:     {len(all_teams)}")
    print(f"  Aliases FS:      {len(existing_aliases)}")
    print(f"  Nomes a resolver: {len(names)}")
    print()

    total_auto = 0
    total_manual = 0
    total_skipped = 0
    total_existing = 0

    for name in names:
        result = await resolve_name(name, all_teams, existing_aliases, pool)
        
        if result["status"] == "already_exists":
            print(f"  ⏭  \"{name}\" → já existe (team_id={result['team_id']})")
            total_existing += 1
            
        elif result["status"] == "exact_match":
            print(f"  ✓  \"{name}\" → {result['canonical']} (exact, id={result['team_id']})")
            total_auto += 1
            
        elif result["status"] == "auto_resolved":
            print(f"  ✓  \"{name}\" → {result['canonical']} (score={result['score']:.0%}, id={result['team_id']})")
            total_auto += 1
            
        elif result["status"] == "needs_input":
            candidates = result["candidates"]
            print(f"\n  ❓ Não resolvido: \"{name}\"")
            print(f"     Candidatos mais próximos:")
            for idx, (t, score) in enumerate(candidates):
                print(f"       [{idx+1}] {t['name_canonical']} (id={t['team_id']}, score={score:.0%})")
            print(f"       [0] Pular")
            print(f"       [m] Digitar team_id manualmente")
            
            choice = input("     Escolha: ").strip()
            
            if choice == "0":
                total_skipped += 1
            elif choice == "m":
                manual_id = input("     team_id: ").strip()
                try:
                    tid = int(manual_id)
                    await save_alias(pool, tid, name)
                    existing_aliases[name.lower()] = tid
                    total_manual += 1
                    print(f"  ✓  Manual: \"{name}\" → team_id {tid}")
                except ValueError:
                    print("  ✗  ID inválido, pulando.")
                    total_skipped += 1
            elif choice.isdigit() and 1 <= int(choice) <= len(candidates):
                selected = candidates[int(choice) - 1][0]
                await save_alias(pool, selected["team_id"], name)
                existing_aliases[name.lower()] = selected["team_id"]
                total_manual += 1
                print(f"  ✓  Selecionado: \"{name}\" → {selected['name_canonical']} (id={selected['team_id']})")
            else:
                total_skipped += 1

    print("\n" + "=" * 60)
    print(f"  RESUMO:")
    print(f"    Auto-resolvidos : {total_auto}")
    print(f"    Manual          : {total_manual}")
    print(f"    Já existiam     : {total_existing}")
    print(f"    Pulados         : {total_skipped}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
