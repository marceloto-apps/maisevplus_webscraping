"""
scripts/resolve_football_data_aliases.py

Resolve aliases pendentes da fonte 'football_data' lendo a tabela unknown_aliases.
Estratégia em cascata:
  1. Correspondência exata com name_canonical do time.
  2. Correspondência exata com alias já cadastrado de outra fonte.
  3. Fuzzy matching >= 87% (SequenceMatcher).
  4. Interface interativa para os restantes.

Uso:
  python scripts/resolve_football_data_aliases.py
  python scripts/resolve_football_data_aliases.py --dry-run   # só mostra, não salva
"""

import asyncio
import sys
import os
import argparse
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

AUTO_THRESHOLD = 0.87


def similarity(a: str, b: str) -> float:
    # Substituir apostrofes inteligentes ou aspas tipográficas por padrão ASCII
    a_clean = a.replace('’', "'").replace('‘', "'").lower().strip()
    b_clean = b.replace('’', "'").replace('‘', "'").lower().strip()
    return SequenceMatcher(None, a_clean, b_clean).ratio()


async def get_all_db_teams(pool) -> list:
    """Retorna todos os times com nome canônico e todos os aliases conhecidos."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT t.team_id, t.name_canonical,
                   array_agg(DISTINCT ta.alias_name) FILTER (WHERE ta.alias_name IS NOT NULL) AS aliases
            FROM teams t
            LEFT JOIN team_aliases ta ON t.team_id = ta.team_id
            GROUP BY t.team_id, t.name_canonical
            ORDER BY t.name_canonical
        """)

    teams = []
    for row in rows:
        search_names = list(row["aliases"] or [])
        if row["name_canonical"] not in search_names:
            search_names.append(row["name_canonical"])
        teams.append({
            "team_id": row["team_id"],
            "name_canonical": row["name_canonical"],
            "search_names": search_names,
        })
    return teams


async def get_existing_aliases(pool, source: str) -> dict:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT alias_name, team_id FROM team_aliases WHERE source = $1", source
        )
    return {r["alias_name"].lower(): r["team_id"] for r in rows}


async def save_alias(pool, team_id: int, alias_name: str, dry_run: bool) -> None:
    if dry_run:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'football_data', $2) ON CONFLICT DO NOTHING",
            team_id, alias_name,
        )
        await conn.execute(
            "DELETE FROM unknown_aliases WHERE source = 'football_data' AND raw_name = $1",
            alias_name,
        )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Mostra resoluções sem salvar no banco")
    args = parser.parse_args()
    dry_run = args.dry_run

    pool = await get_pool()

    async with pool.acquire() as conn:
        unknowns = await conn.fetch(
            "SELECT raw_name FROM unknown_aliases WHERE source = 'football_data' AND resolved = FALSE ORDER BY raw_name ASC"
        )
    api_teams = [r["raw_name"] for r in unknowns]

    all_teams = await get_all_db_teams(pool)
    existing = await get_existing_aliases(pool, "football_data")

    # Configurar stdout para UTF-8 ou usar escape nos prints para evitar UnicodeEncodeError em consoles Windows
    sys.stdout.reconfigure(encoding='utf-8')

    print("\n" + "=" * 65)
    print("  RESOLUTOR DE ALIASES — FOOTBALL-DATA")
    print("=" * 65)
    print(f"  Times no DB:      {len(all_teams)}")
    print(f"  Aliases FD:       {len(existing)}")
    print(f"  Pendentes:        {len(api_teams)}")
    if dry_run:
        print("  MODO DRY-RUN: nenhuma alteração será salva")
    print()

    if not api_teams:
        print("Nenhum alias pendente da Football-Data!")
        return

    total_auto = 0
    total_manual = 0
    total_skipped = 0

    for raw_name in api_teams:
        raw_name = raw_name.strip()
        if not raw_name:
            continue

        raw_lower = raw_name.lower()

        # Já resolvido
        if raw_lower in existing:
            continue

        # 1. Correspondência exata com name_canonical (com tratamento de aspas/apóstrofes inteligentes)
        exact_canonical = next(
            (t for t in all_teams if t["name_canonical"].lower().replace('’', "'").replace('‘', "'") == raw_lower.replace('’', "'").replace('‘', "'")), None
        )
        if exact_canonical:
            await save_alias(pool, exact_canonical["team_id"], raw_name, dry_run)
            existing[raw_lower] = exact_canonical["team_id"]
            total_auto += 1
            tag = "[DRY]" if dry_run else "✓"
            print(f"  {tag} Canônico exato:  \"{raw_name}\" → {exact_canonical['name_canonical']} (id {exact_canonical['team_id']})")
            continue

        # 2. Correspondência exata com alias de qualquer outra fonte
        alias_match = next(
            (t for t in all_teams if any(a.lower().replace('’', "'").replace('‘', "'") == raw_lower.replace('’', "'").replace('‘', "'") for a in t["search_names"])), None
        )
        if alias_match:
            await save_alias(pool, alias_match["team_id"], raw_name, dry_run)
            existing[raw_lower] = alias_match["team_id"]
            total_auto += 1
            tag = "[DRY]" if dry_run else "✓"
            print(f"  {tag} Alias exato:     \"{raw_name}\" → {alias_match['name_canonical']} (id {alias_match['team_id']})")
            continue

        # 3. Fuzzy matching
        scored = []
        for t in all_teams:
            best = max(similarity(raw_name, n) for n in t["search_names"])
            scored.append((t, best))
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:8]
        best_team, best_score = top[0]

        if best_score >= AUTO_THRESHOLD:
            await save_alias(pool, best_team["team_id"], raw_name, dry_run)
            existing[raw_lower] = best_team["team_id"]
            total_auto += 1
            tag = "[DRY]" if dry_run else "✓"
            print(f"  {tag} Fuzzy ({best_score:.0%}):    \"{raw_name}\" → {best_team['name_canonical']} (id {best_team['team_id']})")
            continue

        # 4. Interativo
        print(f"\n  ❓ Não resolvido: \"{raw_name}\"")
        print(f"     Candidatos:")
        for idx, (t, score) in enumerate(top):
            print(f"       [{idx + 1}] {t['name_canonical']} (id={t['team_id']}, score={score:.0%})")
        print(f"       [0] Pular")
        print(f"       [m] Digitar team_id manualmente")

        choice = input("     Escolha: ").strip()

        if choice == "0":
            total_skipped += 1
        elif choice == "m":
            try:
                tid = int(input("     team_id: ").strip())
                await save_alias(pool, tid, raw_name, dry_run)
                existing[raw_lower] = tid
                total_manual += 1
                matched = next((t for t in all_teams if t["team_id"] == tid), None)
                label = matched["name_canonical"] if matched else f"id {tid}"
                print(f"  ✓ Manual:         \"{raw_name}\" → {label}")
            except ValueError:
                print("  ✗ ID inválido, pulando.")
                total_skipped += 1
        elif choice.isdigit() and 1 <= int(choice) <= len(top):
            sel = top[int(choice) - 1][0]
            await save_alias(pool, sel["team_id"], raw_name, dry_run)
            existing[raw_lower] = sel["team_id"]
            total_manual += 1
            print(f"  ✓ Selecionado:    \"{raw_name}\" → {sel['name_canonical']} (id {sel['team_id']})")
        else:
            total_skipped += 1

    print("\n" + "=" * 65)
    print(f"  RESUMO FOOTBALL-DATA:")
    print(f"    Auto-resolvidos : {total_auto}")
    print(f"    Manual          : {total_manual}")
    print(f"    Pulados         : {total_skipped}")
    if dry_run:
        print("  (Dry-run: nenhuma alteração foi salva)")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
