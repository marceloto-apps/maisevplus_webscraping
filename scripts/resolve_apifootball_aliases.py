"""
scripts/resolve_apifootball_aliases.py

Resolve aliases de times da API-Football para o banco de dados.
Para cada liga ativa:
  1. Chama /teams?league={id}&season={year} (1 request por liga).
  2. Tenta auto-match por api_football_id, name_canonical ou aliases existentes.
  3. Para times não resolvidos, mostra candidatos do DB para resolução interativa.
  4. Salva alias em team_aliases e api_football_id em teams.

Uso:
  python scripts/resolve_apifootball_aliases.py [--league CODE]
"""

import asyncio
import sys
import os
import argparse
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db.logger import get_logger
from src.collectors.api_football.client import ApiFootballClient

logger = get_logger("resolve_apifb_aliases")


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def get_all_db_teams(pool) -> list:
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT team_id, name_canonical, api_football_id FROM teams ORDER BY name_canonical")


async def get_existing_aliases(pool) -> dict:
    """Retorna dict de (source, alias_lower) -> team_id"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT source, alias_name, team_id FROM team_aliases WHERE source = 'api_football'")
    return {row["alias_name"].lower(): row["team_id"] for row in rows}


async def get_active_leagues(pool, filter_code=None) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT l.league_id, l.code, l.name, l.api_football_league_id, CAST(LEFT(s.label, 4) AS INTEGER) AS year 
            FROM seasons s 
            JOIN leagues l ON s.league_id = l.league_id 
            WHERE CAST(LEFT(s.label, 4) AS INTEGER) BETWEEN 2021 AND 2024 AND l.api_football_league_id IS NOT NULL
            ORDER BY l.code
        ''')
    leagues = [dict(r) for r in rows]
    if filter_code:
        leagues = [l for l in leagues if l["code"] == filter_code]
    return leagues


async def save_alias(pool, team_id: int, alias_name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'api_football', $2) ON CONFLICT DO NOTHING",
            team_id, alias_name
        )


async def save_api_football_id(pool, team_id: int, api_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE teams SET api_football_id = $1 WHERE team_id = $2 AND (api_football_id IS NULL OR api_football_id != $1)",
            api_id, team_id
        )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", help="Filtrar por código da liga (ex: BRA_SA)", default=None)
    args = parser.parse_args()

    pool = await get_pool()
    all_teams = await get_all_db_teams(pool)
    existing_aliases = await get_existing_aliases(pool)
    leagues = await get_active_leagues(pool, args.league)

    if not leagues:
        print("Nenhuma liga ativa encontrada.")
        return

    print("\n" + "=" * 60)
    print("  RESOLUTOR DE ALIASES — API-FOOTBALL")
    print("=" * 60)
    print(f"  Ligas ativas: {len(leagues)}")
    print(f"  Times no DB:  {len(all_teams)}")
    print(f"  Aliases AF:   {len(existing_aliases)}")
    print()

    total_resolved = 0
    total_skipped = 0
    total_new = 0
    reqs_used = 0

    for league in leagues:
        l_code = league["code"]
        l_api_id = league["api_football_league_id"]
        l_year = league["year"]

        print(f"\n▶ [{l_code}] {league['name']} (API ID: {l_api_id}, Season: {l_year})")
        print("  Buscando times na API...", end=" ", flush=True)

        try:
            api_teams = await ApiFootballClient.get("/teams", {"league": l_api_id, "season": l_year})
            reqs_used += 1
        except Exception as e:
            print(f"ERRO: {e}")
            continue

        print(f"{len(api_teams)} times encontrados.")

        for api_team_data in api_teams:
            team_info = api_team_data.get("team", {})
            api_id = team_info.get("id")
            api_name = team_info.get("name", "")

            if not api_id or not api_name:
                continue

            # ── Tentativa 1: já tem api_football_id no DB ──
            matched_by_id = None
            for t in all_teams:
                if t["api_football_id"] == api_id:
                    matched_by_id = t
                    break

            if matched_by_id:
                # Garante alias
                if api_name.lower() not in existing_aliases:
                    await save_alias(pool, matched_by_id["team_id"], api_name)
                    existing_aliases[api_name.lower()] = matched_by_id["team_id"]
                    total_new += 1
                total_resolved += 1
                continue

            # ── Tentativa 2: alias já existe ──
            if api_name.lower() in existing_aliases:
                db_team_id = existing_aliases[api_name.lower()]
                await save_api_football_id(pool, db_team_id, api_id)
                total_resolved += 1
                continue

            # ── Tentativa 3: match exato por name_canonical ──
            exact = None
            for t in all_teams:
                if t["name_canonical"].lower() == api_name.lower():
                    exact = t
                    break

            if exact:
                await save_alias(pool, exact["team_id"], api_name)
                await save_api_football_id(pool, exact["team_id"], api_id)
                existing_aliases[api_name.lower()] = exact["team_id"]
                total_resolved += 1
                total_new += 1
                print(f"    ✓ Auto: {api_name} → {exact['name_canonical']} (id {exact['team_id']})")
                continue

            # ── Tentativa 4: fuzzy matching — sugere candidatos ──
            scored = [(t, similarity(api_name, t["name_canonical"])) for t in all_teams]
            scored.sort(key=lambda x: x[1], reverse=True)
            top = scored[:8]

            # Auto-aceita se o melhor candidato tiver score >= 0.87
            best_team, best_score = top[0]
            if best_score >= 0.87:
                await save_alias(pool, best_team["team_id"], api_name)
                await save_api_football_id(pool, best_team["team_id"], api_id)
                existing_aliases[api_name.lower()] = best_team["team_id"]
                total_resolved += 1
                total_new += 1
                print(f"    ✓ Auto-fuzzy ({best_score:.0%}): \"{api_name}\" → {best_team['name_canonical']} (id {best_team['team_id']})")
                continue

            print(f"\n    ❓ Não resolvido: \"{api_name}\" (api_id={api_id})")
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
                    await save_alias(pool, tid, api_name)
                    await save_api_football_id(pool, tid, api_id)
                    existing_aliases[api_name.lower()] = tid
                    total_resolved += 1
                    total_new += 1
                    print(f"    ✓ Manual: {api_name} → team_id {tid}")
                except ValueError:
                    print("    ✗ ID inválido, pulando.")
                    total_skipped += 1
            elif choice.isdigit() and 1 <= int(choice) <= len(top):
                selected = top[int(choice) - 1][0]
                await save_alias(pool, selected["team_id"], api_name)
                await save_api_football_id(pool, selected["team_id"], api_id)
                existing_aliases[api_name.lower()] = selected["team_id"]
                total_resolved += 1
                total_new += 1
                print(f"    ✓ Selecionado: {api_name} → {selected['name_canonical']} (id {selected['team_id']})") 
            else:
                total_skipped += 1

    print("\n" + "=" * 60)
    print(f"  RESUMO:")
    print(f"    Resolvidos : {total_resolved}")
    print(f"    Novos alias: {total_new}")
    print(f"    Pulados    : {total_skipped}")
    print(f"    API reqs   : {reqs_used}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
