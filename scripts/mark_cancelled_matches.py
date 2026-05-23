"""
scripts/mark_cancelled_matches.py

Marca como 'cancelled' as partidas identificadas como fixtures canceladas/adiadas
que nunca receberão resultado (não aparecem nos CSVs de resultado das fontes).

Partidas marcadas:
  1. Blackburn vs Ipswich      (Championship, 2025-09-20) — Ipswich estava no PL em 25/26
  2. Bastia vs Red Star         (Ligue 2, 2025-12-05)     — Problemas administrativos
  3. Botafogo vs Vitoria        (Brasileirão, 2026-02-24)  — Data anômala para Série A
  4. Bahia vs Chapecoense       (Brasileirão, 2026-02-24)  — Chapecoense não é da Série A 2026
  5. Flamengo vs Mirassol       (Brasileirão, 2026-02-24)  — Mesma data anômala

Uso:
  python scripts/mark_cancelled_matches.py
  python scripts/mark_cancelled_matches.py --dry-run
"""

import asyncio
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

CANCELLED_MATCH_IDS = [
    # (match_id, home, away, reason)
    (
        "051b90de-f444-41e5-8aae-32b02dfea979",
        "Blackburn", "Ipswich",
        "Championship 2025-09-20 — Ipswich estava no Premier League em 25/26"
    ),
    (
        "83206413-f7b8-487f-9b53-5f28318560df",
        "Bastia", "Red Star",
        "Ligue 2 2025-12-05 — Problemas administrativos dos clubes"
    ),
    (
        "24f9a0c7-00b2-46f3-a885-247bf26d0db5",
        "Botafogo", "Vitoria",
        "Brasileirão 2026-02-24 — Data anômala, Série A começa em abril"
    ),
    (
        "a8a4a533-0acf-48ff-b384-187e50655178",
        "Bahia", "Chapecoense",
        "Brasileirão 2026-02-24 — Chapecoense não disputa a Série A 2026"
    ),
    (
        "29aeab55-ac22-44bf-849e-feef1a746218",
        "Flamengo", "Mirassol",
        "Brasileirão 2026-02-24 — Data anômala, mesma rodada cancelada"
    ),
]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Mostra o que seria feito sem alterar o banco")
    args = parser.parse_args()
    dry_run = args.dry_run

    pool = await get_pool()

    print("\n" + "=" * 65)
    print("  MARK CANCELLED MATCHES")
    if dry_run:
        print("  MODO DRY-RUN — nenhuma alteração será salva")
    print("=" * 65)

    updated = 0
    not_found = 0

    async with pool.acquire() as conn:
        for match_id, home, away, reason in CANCELLED_MATCH_IDS:
            # Verifica estado atual
            row = await conn.fetchrow(
                "SELECT status, kickoff FROM matches WHERE match_id = $1",
                match_id
            )
            if not row:
                print(f"  ✗ NOT FOUND  {home} vs {away} — match_id {match_id}")
                not_found += 1
                continue

            current_status = row["status"]
            kickoff = row["kickoff"]

            if current_status == "cancelled":
                print(f"  - JÁ CANCELADO  {home} vs {away} ({kickoff.date()})")
                continue

            if not dry_run:
                await conn.execute(
                    """
                    UPDATE matches
                    SET status     = 'cancelled',
                        updated_at = NOW()
                    WHERE match_id = $1
                    """,
                    match_id,
                )
                tag = "✓ CANCELADO"
            else:
                tag = "[DRY] CANCELARIA"

            print(f"  {tag}  {home} vs {away} ({kickoff.date()}) [era: {current_status}]")
            print(f"         Motivo: {reason}")
            updated += 1

    print("\n" + "=" * 65)
    print(f"  Atualizados : {updated}")
    print(f"  Não encontrados: {not_found}")
    if dry_run:
        print("  (Dry-run: nenhuma alteração foi salva)")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
