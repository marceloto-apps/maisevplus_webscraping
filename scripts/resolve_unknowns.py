"""
scripts/resolve_unknowns.py
Busca os team_ids candidatos para aliases desconhecidos e insere os mapeamentos.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool


async def run():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Listar unknown_aliases pendentes
        unknowns = await conn.fetch(
            "SELECT source, raw_name FROM unknown_aliases ORDER BY first_seen DESC LIMIT 10"
        )
        print("=== ALIASES DESCONHECIDOS ===\n")
        for u in unknowns:
            print(f"  {u['source']:20s} | {u['raw_name']}")

        print("\n=== BUSCANDO CANDIDATOS ===\n")

        searches = [
            ("Young Boys", "young boys"),
            ("Kings Lynn", "king"),
            ("Twente", "twente"),
            ("Huesca", "huesca"),
            ("Nacional", "nacional"),
            ("Lecce", "lecce"),
            ("Gil-Vicente-FC", "gil vicente"),
            ("PSV", "psv"),
            ("Altrincham", "altrincham"),
            ("Boreham-Wood", "boreham"),
        ]

        for label, term in searches:
            rows = await conn.fetch(
                "SELECT t.team_id, t.name_canonical FROM teams t "
                "WHERE LOWER(t.name_canonical) LIKE '%' || $1 || '%'",
                term,
            )
            print(f"--- {label} ---")
            for r in rows:
                print(f"  {r['team_id']:5d} | {r['name_canonical']}")

            if not rows:
                rows2 = await conn.fetch(
                    "SELECT ta.team_id, t.name_canonical, ta.alias_name "
                    "FROM team_aliases ta JOIN teams t ON t.team_id = ta.team_id "
                    "WHERE LOWER(ta.alias_name) LIKE '%' || $1 || '%' LIMIT 5",
                    term,
                )
                for r in rows2:
                    print(f"  {r['team_id']:5d} | {r['name_canonical']} (alias: {r['alias_name']})")

            if not rows:
                print("  (nenhum candidato encontrado)")
            print()


if __name__ == "__main__":
    asyncio.run(run())
