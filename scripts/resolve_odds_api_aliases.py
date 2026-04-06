"""
resolve_odds_api_aliases.py
Mapeia nomes de times da Odds API para os IDs canônicos do banco.
Usa o endpoint /events (sem odds) para minimizar consumo de créditos.

Uso:
  python scripts/resolve_odds_api_aliases.py
  python scripts/resolve_odds_api_aliases.py --league ENG_PL
"""

import argparse
import asyncio
import os
import sys
import yaml
from difflib import SequenceMatcher

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.scheduler.key_manager import KeyManager
from src.db.logger import get_logger

logger = get_logger(__name__)

SOURCE = "odds_api"


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def get_all_db_teams(pool) -> list:
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT team_id, name_canonical FROM teams ORDER BY name_canonical")


async def get_existing_aliases(pool) -> dict:
    """Retorna dict de alias_lower -> team_id para source='odds_api'"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT alias_name, team_id FROM team_aliases WHERE source = $1", SOURCE)
    return {row["alias_name"].lower(): row["team_id"] for row in rows}


async def get_all_aliases(pool) -> dict:
    """Retorna dict de alias_lower -> team_id para QUALQUER source (para cross-match)"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT alias_name, team_id FROM team_aliases")
    result = {}
    for row in rows:
        result[row["alias_name"].lower()] = row["team_id"]
    return result


def load_leagues_config() -> dict:
    yaml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "config", "leagues.yaml")
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f).get("leagues", {})


async def fetch_events(sport_key: str, api_key: str) -> list:
    """Busca eventos do endpoint /events (sem odds, custo mínimo)."""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events"
    params = {"apiKey": api_key}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        # Mostra créditos restantes
        remaining = resp.headers.get("x-requests-remaining", "?")
        used = resp.headers.get("x-requests-used", "?")
        cost = resp.headers.get("x-requests-last", "?")
        print(f"     [Créditos] Usados: {used} | Restantes: {remaining} | Custo desta chamada: {cost}")
        resp.raise_for_status()
        return resp.json()


async def save_alias(pool, team_id: int, alias_name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            team_id, SOURCE, alias_name
        )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", help="Filtrar por código da liga (ex: ENG_PL)", default=None)
    args = parser.parse_args()

    pool = await get_pool()
    all_teams = await get_all_db_teams(pool)
    existing_aliases = await get_existing_aliases(pool)
    all_source_aliases = await get_all_aliases(pool)
    leagues_config = load_leagues_config()

    # Filtra ligas que têm odds_api_sport_key
    target_leagues = []
    for code, conf in leagues_config.items():
        sport_key = conf.get("odds_api_sport_key")
        if not sport_key:
            continue
        if args.league and code != args.league:
            continue
        target_leagues.append({"code": code, "name": conf["name"], "sport_key": sport_key})

    if not target_leagues:
        print("Nenhuma liga com odds_api_sport_key encontrada.")
        return

    # Reativa temporariamente 1 chave para buscar eventos
    async with pool.acquire() as conn:
        key_row = await conn.fetchrow("SELECT key_id, key_value FROM api_keys WHERE service = 'odds_api' ORDER BY key_id LIMIT 1")
        if not key_row:
            print("❌ Nenhuma chave odds_api encontrada no banco!")
            return
        api_key = key_row["key_value"]

    print("\n" + "=" * 60)
    print("  RESOLUTOR DE ALIASES — ODDS API")
    print("=" * 60)
    print(f"  Ligas alvo:    {len(target_leagues)}")
    print(f"  Times no DB:   {len(all_teams)}")
    print(f"  Aliases OA:    {len(existing_aliases)}")
    print(f"  Aliases total: {len(all_source_aliases)}")
    print()

    total_resolved = 0
    total_skipped = 0
    total_new = 0
    total_auto = 0
    reqs_used = 0

    for league in target_leagues:
        l_code = league["code"]
        sport_key = league["sport_key"]

        print(f"\n▶ [{l_code}] {league['name']} (sport_key: {sport_key})")
        print("  Buscando eventos na Odds API...", flush=True)

        try:
            events = await fetch_events(sport_key, api_key)
            reqs_used += 1
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                print(f"  ⚠️ Liga não disponível na Odds API (422). Pulando.")
            else:
                print(f"  ❌ ERRO HTTP: {e.response.status_code}")
            continue
        except Exception as e:
            print(f"  ❌ ERRO: {e}")
            continue

        if not events:
            print(f"  ↳ 0 eventos retornados.")
            continue

        # Extrair nomes ÚNICOS
        unique_names = set()
        for ev in events:
            if ev.get("home_team"):
                unique_names.add(ev["home_team"])
            if ev.get("away_team"):
                unique_names.add(ev["away_team"])

        print(f"  ↳ {len(events)} eventos, {len(unique_names)} times únicos.")

        for api_name in sorted(unique_names):
            # ── Tentativa 1: Alias odds_api já existe ──
            if api_name.lower() in existing_aliases:
                total_resolved += 1
                continue

            # ── Tentativa 2: Match exato por name_canonical ──
            exact = None
            for t in all_teams:
                if t["name_canonical"].lower() == api_name.lower():
                    exact = t
                    break

            if exact:
                await save_alias(pool, exact["team_id"], api_name)
                existing_aliases[api_name.lower()] = exact["team_id"]
                total_resolved += 1
                total_new += 1
                total_auto += 1
                print(f"    ✓ Auto (exato): {api_name} → {exact['name_canonical']} (id {exact['team_id']})")
                continue

            # ── Tentativa 3: Cross-match com aliases de OUTRAS fontes ──
            if api_name.lower() in all_source_aliases:
                tid = all_source_aliases[api_name.lower()]
                await save_alias(pool, tid, api_name)
                existing_aliases[api_name.lower()] = tid
                total_resolved += 1
                total_new += 1
                total_auto += 1
                # Busca nome canônico para exibição
                canonical = next((t["name_canonical"] for t in all_teams if t["team_id"] == tid), "?")
                print(f"    ✓ Auto (cross): {api_name} → {canonical} (id {tid})")
                continue

            # ── Tentativa 4: Fuzzy matching ──
            scored = [(t, similarity(api_name, t["name_canonical"])) for t in all_teams]
            scored.sort(key=lambda x: x[1], reverse=True)
            top = scored[:5]

            # Auto-accept se score >= 0.90
            if top[0][1] >= 0.90:
                best = top[0][0]
                await save_alias(pool, best["team_id"], api_name)
                existing_aliases[api_name.lower()] = best["team_id"]
                total_resolved += 1
                total_new += 1
                total_auto += 1
                print(f"    ✓ Auto (fuzzy {top[0][1]:.2f}): {api_name} → {best['name_canonical']} (id {best['team_id']})")
                continue

            # ── Tentativa 5: Resolução manual ──
            print(f"\n    ❓ Não resolvido: \"{api_name}\"")
            print(f"       Candidatos mais próximos:")
            for idx, (t, score) in enumerate(top):
                print(f"         [{idx+1}] {t['name_canonical']} (id={t['team_id']}, score={score:.2f})")
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
                existing_aliases[api_name.lower()] = selected["team_id"]
                total_resolved += 1
                total_new += 1
                print(f"    ✓ Selecionado: {api_name} → {selected['name_canonical']} (id {selected['team_id']})")
            else:
                total_skipped += 1

    print("\n" + "=" * 60)
    print(f"  RESUMO:")
    print(f"    Resolvidos  : {total_resolved}")
    print(f"    Novos alias : {total_new}")
    print(f"    Auto-match  : {total_auto}")
    print(f"    Pulados     : {total_skipped}")
    print(f"    API reqs    : {reqs_used}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
