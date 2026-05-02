"""
scripts/resolve_fpt_aliases.py

Resolve aliases de times da FutPythonTrader (FPT) para o banco de dados.
Como a FPT não possui um endpoint de listagem de times, ele baixa o CSV
da temporada atual da liga, extrai os nomes únicos e passa pela mesma lógica interativa.

Uso:
  python scripts/resolve_fpt_aliases.py [--league CODE]
"""

import asyncio
import sys
import os
import argparse
from difflib import SequenceMatcher
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db.logger import get_logger
# Importamos a mesma classe base ou refazemos o fetch_fpt_data aqui para independência
from scripts.fpt_flashscore_stats_backfill import FPTStatsBackfill, FPT_LEAGUE_MAP

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
            # Adiciona o nome canônico na lista de nomes comparáveis
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


async def get_active_leagues(pool, filter_code=None) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT l.league_id, l.code, l.name, s.label AS season_label 
            FROM seasons s 
            JOIN leagues l ON s.league_id = l.league_id 
            WHERE s.is_current = TRUE
            ORDER BY l.code
        ''')
    leagues = [dict(r) for r in rows]
    if filter_code:
        leagues = [l for l in leagues if l["code"] == filter_code]
    return leagues


async def save_alias(pool, team_id: int, alias_name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'fpt', $2) ON CONFLICT DO NOTHING",
            team_id, alias_name
        )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", help="Filtrar por código da liga (ex: BRA_SA)", default=None)
    args = parser.parse_args()

    pool = await get_pool()
    all_teams = await get_all_db_teams(pool)
    existing_aliases_fpt = await get_existing_aliases(pool, 'fpt')
    existing_aliases_footystats = await get_existing_aliases(pool, 'footystats')
    leagues = await get_active_leagues(pool, args.league)

    if not leagues:
        print("Nenhuma liga ativa encontrada.")
        return

    try:
        fpt_client = FPTStatsBackfill()
    except Exception as e:
        print(f"Erro ao iniciar cliente FPT: {e}")
        return

    print("\n" + "=" * 60)
    print("  RESOLUTOR DE ALIASES — FUTPYTHONTRADER (FPT)")
    print("=" * 60)
    print(f"  Ligas ativas: {len(leagues)}")
    print(f"  Times no DB:  {len(all_teams)}")
    print(f"  Aliases FPT:  {len(existing_aliases_fpt)}")
    print()

    total_resolved = 0
    total_skipped = 0
    total_new = 0
    reqs_used = 0

    for league in leagues:
        l_code = league["code"]
        season_label = league["season_label"]
        fpt_league = FPT_LEAGUE_MAP.get(l_code)

        if not fpt_league:
            print(f"▶ [{l_code}] Sem mapeamento para FPT. Pulando.")
            continue

        print(f"\n▶ [{l_code}] {league['name']} (FPT: {fpt_league}, Season: {season_label})")
        print("  Baixando CSV de dados da API FPT...", end=" ", flush=True)

        fpt_season = fpt_client._convert_season_label(season_label)
        df = fpt_client.fetch_fpt_data(fpt_league, fpt_season)
        reqs_used += 1

        if df.empty:
            print("Vazio ou Erro.")
            continue
        
        # Extrai nomes únicos de times
        home_teams = df['Home'].dropna().unique().tolist() if 'Home' in df.columns else []
        away_teams = df['Away'].dropna().unique().tolist() if 'Away' in df.columns else []
        api_teams = list(set(home_teams + away_teams))

        print(f"{len(api_teams)} times únicos encontrados no arquivo.")

        for api_name in api_teams:
            api_name = str(api_name).strip()
            if not api_name:
                continue

            # ── Tentativa 1: alias já existe no fpt ──
            if api_name.lower() in existing_aliases_fpt:
                total_resolved += 1
                continue

            # ── Tentativa 2: alias existe no footystats (FPT puxa do Footystats) ──
            if api_name.lower() in existing_aliases_footystats:
                db_team_id = existing_aliases_footystats[api_name.lower()]
                await save_alias(pool, db_team_id, api_name)
                existing_aliases_fpt[api_name.lower()] = db_team_id
                total_resolved += 1
                total_new += 1
                exact = next((t for t in all_teams if t['team_id'] == db_team_id), None)
                print(f"    ✓ Auto (Footystats inherit): {api_name} → {exact['name_canonical'] if exact else db_team_id} (id {db_team_id})")
                continue

            # ── Tentativa 3: match exato por name_canonical ──
            exact = None
            for t in all_teams:
                if t["name_canonical"].lower() == api_name.lower():
                    exact = t
                    break

            if exact:
                await save_alias(pool, exact["team_id"], api_name)
                existing_aliases_fpt[api_name.lower()] = exact["team_id"]
                total_resolved += 1
                total_new += 1
                print(f"    ✓ Auto (Canonical): {api_name} → {exact['name_canonical']} (id {exact['team_id']})")
                continue

            # ── Tentativa 4: fuzzy matching usando TODOS os aliases do time ──
            scored = []
            for t in all_teams:
                # Calcula a similaridade contra o nome canônico e todos os aliases conhecidos
                best_score = max(similarity(api_name, name) for name in t["search_names"])
                scored.append((t, best_score))
                
            scored.sort(key=lambda x: x[1], reverse=True)
            top = scored[:8]

            # Auto-aceita se o melhor candidato tiver score >= 0.87
            best_team, best_score = top[0]
            if best_score >= 0.87:
                await save_alias(pool, best_team["team_id"], api_name)
                existing_aliases_fpt[api_name.lower()] = best_team["team_id"]
                total_resolved += 1
                total_new += 1
                print(f"    ✓ Auto-fuzzy ({best_score:.0%}): \"{api_name}\" → {best_team['name_canonical']} (id {best_team['team_id']})")
                continue

            print(f"\n    ❓ Não resolvido: \"{api_name}\"")
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
                    existing_aliases_fpt[api_name.lower()] = tid
                    total_resolved += 1
                    total_new += 1
                    print(f"    ✓ Manual: {api_name} → team_id {tid}")
                except ValueError:
                    print("    ✗ ID inválido, pulando.")
                    total_skipped += 1
            elif choice.isdigit() and 1 <= int(choice) <= len(top):
                selected = top[int(choice) - 1][0]
                await save_alias(pool, selected["team_id"], api_name)
                existing_aliases_fpt[api_name.lower()] = selected["team_id"]
                total_resolved += 1
                total_new += 1
                print(f"    ✓ Selecionado: {api_name} → {selected['name_canonical']} (id {selected['team_id']})") 
            else:
                total_skipped += 1

    print("\n" + "=" * 60)
    print(f"  RESUMO FPT:")
    print(f"    Resolvidos : {total_resolved}")
    print(f"    Novos alias: {total_new}")
    print(f"    Pulados    : {total_skipped}")
    print(f"    API reqs   : {reqs_used}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
