"""
scripts/run_flashscore_discovery_historical.py

Discovery de Flashscore IDs para TODAS as temporadas históricas.
Processa da temporada mais nova para a mais antiga, pulando temporadas
que já foram 100% mapeadas.

Este script é para execução manual (uma ou mais vezes) até que
todos os flashscore_ids sejam descobertos. Após cada rodada,
resolver os unknown_aliases pendentes e rodar novamente.

Uso:
    xvfb-run -a python scripts/run_flashscore_discovery_historical.py
    xvfb-run -a python scripts/run_flashscore_discovery_historical.py --leagues ENG_PL BRA_SA
    xvfb-run -a python scripts/run_flashscore_discovery_historical.py --seasons 2024/2025 2023/2024
    xvfb-run -a python scripts/run_flashscore_discovery_historical.py --leagues ENG_PL --seasons 2023/2024
    xvfb-run -a python scripts/run_flashscore_discovery_historical.py --dry-run
"""
import asyncio
import os
import sys
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from src.collectors.flashscore.discovery import FlashscoreDiscovery
from src.collectors.flashscore.config import LEAGUE_FLASHSCORE_PATHS
from src.db.pool import get_pool
from src.db.logger import get_logger

logger = get_logger(__name__)


def build_flashscore_season_slug(label: str) -> str:
    """
    Converte label de temporada para slug de URL do Flashscore.
    Exemplos:
        '2024/2025' -> '2024-2025'
        '2025'      -> '2025'
        '24/25'     -> '2024-2025'  (fallback legado)
    """
    if "/" in label:
        parts = label.split("/")
        p1, p2 = parts[0].strip(), parts[1].strip()
        y1 = f"20{p1}" if len(p1) == 2 else p1
        y2 = f"20{p2}" if len(p2) == 2 else p2
        return f"{y1}-{y2}"
    return label


async def main():
    parser = argparse.ArgumentParser(description="Flashscore Historical Discovery (All Seasons)")
    parser.add_argument(
        "--leagues", nargs="*", default=None,
        help="Ligas específicas (ex: ENG_PL BRA_SA). Se omitido, roda todas."
    )
    parser.add_argument(
        "--seasons", nargs="*", default=None,
        help="Temporadas específicas (ex: 2024/2025 2023/2024 2025). Se omitido, roda todas."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Apenas mostra as URLs que seriam acessadas, sem navegar."
    )
    args = parser.parse_args()

    from src.alerts.telegram_mini import TelegramAlert
    await TelegramAlert.init()

    print("=" * 70)
    print("  FLASHSCORE HISTORICAL DISCOVERY — ALL SEASONS (Newest → Oldest)")
    print("=" * 70)

    pool = await get_pool()
    target_urls = {}
    skipped_seasons = 0
    total_season_urls = 0

    # Filtra ligas: usa o dicionário LEAGUE_FLASHSCORE_PATHS como fonte dos paths
    if args.leagues:
        league_codes = [c for c in args.leagues if c in LEAGUE_FLASHSCORE_PATHS]
    else:
        league_codes = list(LEAGUE_FLASHSCORE_PATHS.keys())

    async with pool.acquire() as conn:
        for code in league_codes:
            base_path = LEAGUE_FLASHSCORE_PATHS[code]

            # Busca league_id
            league_id = await conn.fetchval(
                "SELECT league_id FROM leagues WHERE code = $1 AND is_active = TRUE", code
            )
            if not league_id:
                print(f"  [WARN] Liga {code} não encontrada/inativa no banco. Pulando.")
                continue

            # Busca TODAS as temporadas, da mais nova para a mais antiga
            seasons = await conn.fetch("""
                SELECT s.season_id, s.label, s.is_current
                FROM seasons s
                WHERE s.league_id = $1
                ORDER BY s.label DESC
            """, league_id)

            urls = []
            for s in seasons:
                season_id = s["season_id"]
                label = s["label"]
                is_current = s.get("is_current", False)

                # Filtra por temporada se especificado
                if args.seasons and label not in args.seasons:
                    continue

                # Verifica progresso por temporada
                pending = await conn.fetchval("""
                    SELECT count(*)
                    FROM matches
                    WHERE season_id = $1
                      AND status = 'finished'
                      AND flashscore_id IS NULL
                """, season_id)

                total_in_season = await conn.fetchval("""
                    SELECT count(*)
                    FROM matches
                    WHERE season_id = $1
                      AND status = 'finished'
                """, season_id)

                already_mapped = total_in_season - pending

                if pending == 0:
                    pct_text = "100%" if total_in_season > 0 else "vazio"
                    print(f"  [SKIP] {code} / {label}: "
                          f"{already_mapped}/{total_in_season} ({pct_text}). Pulando.")
                    skipped_seasons += 1
                    continue

                pct = round(already_mapped / total_in_season * 100, 1) if total_in_season > 0 else 0

                # Constrói a URL para esta temporada
                if is_current:
                    url = f"https://www.flashscore.com/{base_path}/results/"
                else:
                    slug = build_flashscore_season_slug(label)
                    url = f"https://www.flashscore.com/{base_path}-{slug}/results/"

                print(f"  [QUEUE] {code} / {label}: "
                      f"{already_mapped}/{total_in_season} ({pct}%). "
                      f"{pending} pendentes."
                      f"\n          URL: {url}")
                urls.append(url)

            if urls:
                target_urls[code] = urls
                total_season_urls += len(urls)

    print(f"\n{'=' * 70}")
    print(f"  Alvos: {len(target_urls)} ligas, {total_season_urls} temporadas pendentes")
    print(f"  Pulados: {skipped_seasons} temporadas completas (100%)")
    print(f"{'=' * 70}\n")

    if not target_urls:
        print("[Discovery] Nenhuma temporada com partidas pendentes. Nada a fazer.")
        TelegramAlert.fire("info", "🔍 *Flashscore Historical Discovery*\nNenhuma temporada pendente.")
        await asyncio.sleep(1)
        await TelegramAlert.close()
        return

    if args.dry_run:
        print("[DRY-RUN] Nenhuma navegação realizada. Verifique as URLs acima.")
        await TelegramAlert.close()
        return

    # Executa o discovery
    discovery = FlashscoreDiscovery()
    res = await discovery.collect(
        mode="results",
        specific_leagues=list(target_urls.keys()),
        target_urls=target_urls
    )

    print(f"\n{'=' * 70}")
    print(f"  DISCOVERY HISTÓRICO CONCLUÍDO!")
    print(f"  Status: {res.status.name}")
    print(f"  Matches associados: {res.records_new}")
    print(f"  Erros: {len(res.errors)}")
    print(f"{'=' * 70}")

    if res.errors:
        print("\n  Erros detalhados:")
        for i, err in enumerate(res.errors[:10], 1):
            print(f"    {i}. {err[:200]}")

    # Verifica unknowns pendentes
    async with pool.acquire() as conn:
        unknowns = await conn.fetch(
            "SELECT source, raw_name, league_code FROM unknown_aliases "
            "WHERE source = 'flashscore' AND resolved = FALSE "
            "ORDER BY first_seen DESC LIMIT 20"
        )

    if unknowns:
        print(f"\n{'=' * 70}")
        print(f"  ⚠️  {len(unknowns)} ALIASES NÃO RESOLVIDOS (flashscore)")
        print(f"  Resolva-os e rode este script novamente para completar o mapeamento.")
        print(f"{'=' * 70}")
        for u in unknowns[:15]:
            print(f"    [{u['league_code'] or '?'}] {u['raw_name']}")
        if len(unknowns) > 15:
            print(f"    ... e mais {len(unknowns) - 15}")

    msg = (
        f"🔍 *Flashscore Historical Discovery*\n"
        f"Status: `{res.status.name}`\n"
        f"Temporadas processadas: `{total_season_urls}`\n"
        f"Temporadas puladas (100%): `{skipped_seasons}`\n"
        f"Matches Associados: `{res.records_new}`\n"
        f"Unknowns pendentes: `{len(unknowns)}`"
    )
    if res.status.name == "FAILED":
        TelegramAlert.fire("error", msg)
    else:
        TelegramAlert.fire("info", msg)

    await asyncio.sleep(1)
    await TelegramAlert.close()


if __name__ == "__main__":
    asyncio.run(main())
