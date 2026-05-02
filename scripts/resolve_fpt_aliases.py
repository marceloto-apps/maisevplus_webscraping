"""
scripts/resolve_fpt_aliases.py

Resolve aliases pendentes da FutPythonTrader (FPT) lendo a tabela unknown_aliases.
Aplica a mesma lógica avançada de fuzzy matching baseada em aliases e remove
da fila os itens resolvidos.

Uso:
  python scripts/resolve_fpt_aliases.py
"""

import asyncio
import sys
import os
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db.logger import get_logger

logger = get_logger("resolve_fpt_aliases")


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def get_all_db_teams(pool) -> list:
    async with pool.acquire() as conn:
        # Puxa o nome canônico e todos os aliases conhecidos para cada team_id
        rows = await conn.fetch("""
            SELECT t.team_id, t.name_canonical, 
                   array_agg(DISTINCT ta.alias_name) FILTER (WHERE ta.alias_name IS NOT NULL) as aliases
            FROM teams t
            LEFT JOIN team_aliases ta ON t.team_id = ta.team_id
            GROUP BY t.team_id, t.name_canonical
            ORDER BY t.name_canonical
        """)
        
        teams = []
        for row in rows:
            aliases = row["aliases"] or []
            if row["name_canonical"] not in aliases:
                aliases.append(row["name_canonical"])
            
            teams.append({
                "team_id": row["team_id"],
                "name_canonical": row["name_canonical"],
                "search_names": aliases
            })
        return teams


async def get_existing_aliases(pool, source: str) -> dict:
    """Retorna dict de alias_lower -> team_id"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT alias_name, team_id FROM team_aliases WHERE source = $1", source)
    return {row["alias_name"].lower(): row["team_id"] for row in rows}


async def save_alias(pool, team_id: int, alias_name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'fpt', $2) ON CONFLICT DO NOTHING",
            team_id, alias_name
        )

async def remove_from_unknown(pool, raw_name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM unknown_aliases WHERE source = 'fpt' AND raw_name = $1",
            raw_name
        )


async def main():
    pool = await get_pool()
    all_teams = await get_all_db_teams(pool)
    existing_aliases_fpt = await get_existing_aliases(pool, 'fpt')
    existing_aliases_footystats = await get_existing_aliases(pool, 'footystats')

    async with pool.acquire() as conn:
        unknowns = await conn.fetch("SELECT raw_name FROM unknown_aliases WHERE source = 'fpt' ORDER BY first_seen ASC")
    
    api_teams = [row["raw_name"] for row in unknowns]

    print("\n" + "=" * 60)
    print("  RESOLUTOR DE ALIASES — FUTPYTHONTRADER (FPT)")
    print("=" * 60)
    print(f"  Times no DB:     {len(all_teams)}")
    print(f"  Aliases FPT:     {len(existing_aliases_fpt)}")
    print(f"  Pendentes (FPT): {len(api_teams)}")
    print()

    if not api_teams:
        print("🎉 Nenhum alias FPT pendente de resolução na tabela unknown_aliases!")
        return

    total_resolved = 0
    total_skipped = 0
    total_new = 0

    for api_name in api_teams:
        api_name_str = str(api_name).strip()
        if not api_name_str:
            continue

        # ── Tentativa 1: alias já existe no fpt ──
        if api_name_str.lower() in existing_aliases_fpt:
            await remove_from_unknown(pool, api_name_str)
            total_resolved += 1
            continue

        # ── Tentativa 2: alias existe no footystats (FPT puxa do Footystats) ──
        if api_name_str.lower() in existing_aliases_footystats:
            db_team_id = existing_aliases_footystats[api_name_str.lower()]
            await save_alias(pool, db_team_id, api_name_str)
            await remove_from_unknown(pool, api_name_str)
            existing_aliases_fpt[api_name_str.lower()] = db_team_id
            total_resolved += 1
            total_new += 1
            exact = next((t for t in all_teams if t['team_id'] == db_team_id), None)
            print(f"    ✓ Auto (Footystats inherit): {api_name_str} → {exact['name_canonical'] if exact else db_team_id} (id {db_team_id})")
            continue

        # ── Tentativa 3: match exato por name_canonical ──
        exact = None
        for t in all_teams:
            if t["name_canonical"].lower() == api_name_str.lower():
                exact = t
                break

        if exact:
            await save_alias(pool, exact["team_id"], api_name_str)
            await remove_from_unknown(pool, api_name_str)
            existing_aliases_fpt[api_name_str.lower()] = exact["team_id"]
            total_resolved += 1
            total_new += 1
            print(f"    ✓ Auto (Canonical): {api_name_str} → {exact['name_canonical']} (id {exact['team_id']})")
            continue

        # ── Tentativa 4: fuzzy matching usando TODOS os aliases do time ──
        scored = []
        for t in all_teams:
            best_score = max(similarity(api_name_str, name) for name in t["search_names"])
            scored.append((t, best_score))
            
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:8]

        best_team, best_score = top[0]
        if best_score >= 0.87:
            await save_alias(pool, best_team["team_id"], api_name_str)
            await remove_from_unknown(pool, api_name_str)
            existing_aliases_fpt[api_name_str.lower()] = best_team["team_id"]
            total_resolved += 1
            total_new += 1
            print(f"    ✓ Auto-fuzzy ({best_score:.0%}): \"{api_name_str}\" → {best_team['name_canonical']} (id {best_team['team_id']})")
            continue

        print(f"\n    ❓ Não resolvido: \"{api_name_str}\"")
        print(f"       Candidatos mais próximos:")
        for idx, (t, score) in enumerate(top):
            print(f"         [{idx+1}] {t['name_canonical']} (id={t['team_id']}, score={score:.0%})")
        print(f"         [0] Pular")
        print(f"         [m] Digitar team_id manualmente")

        choice = input("       Escolha: ").strip()

        if choice == "0":
            total_skipped += 1
            continue
        elif choice == "m":
            manual_id = input("       team_id: ").strip()
            try:
                tid = int(manual_id)
                await save_alias(pool, tid, api_name_str)
                await remove_from_unknown(pool, api_name_str)
                existing_aliases_fpt[api_name_str.lower()] = tid
                total_resolved += 1
                total_new += 1
                print(f"    ✓ Manual: {api_name_str} → team_id {tid}")
            except ValueError:
                print("    ✗ ID inválido, pulando.")
                total_skipped += 1
        elif choice.isdigit() and 1 <= int(choice) <= len(top):
            selected = top[int(choice) - 1][0]
            await save_alias(pool, selected["team_id"], api_name_str)
            await remove_from_unknown(pool, api_name_str)
            existing_aliases_fpt[api_name_str.lower()] = selected["team_id"]
            total_resolved += 1
            total_new += 1
            print(f"    ✓ Selecionado: {api_name_str} → {selected['name_canonical']} (id {selected['team_id']})") 
        else:
            total_skipped += 1

    print("\n" + "=" * 60)
    print(f"  RESUMO FPT:")
    print(f"    Resolvidos : {total_resolved}")
    print(f"    Novos alias: {total_new}")
    print(f"    Pulados    : {total_skipped}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
