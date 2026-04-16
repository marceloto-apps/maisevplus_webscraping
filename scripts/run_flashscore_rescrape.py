"""
scripts/run_flashscore_rescrape.py

Script de contingência para DELETAR e re-capturar odds AH e OU do Flashscore.
Necessário após fix do parser (commit 05e5a6a) que corrigiu:
  - Linhas inteiras (0, 1, 2, -3) ignoradas
  - Quarter-goals (-1.25, 2.25) ignoradas
  - Handicap 0 (célula ausente no DOM) ignorado
  - Odds confundidas com linhas (1.16, 1.57 etc.)

Os flashscore_id ficam preservados na tabela `matches` — são o link 
de cada jogo para navegação/scraping.

Estratégia:
  1. DELETA odds AH e OU com source='flashscore' da odds_history
  2. Reseta flag scraping_flashscore = false para forçar re-coleta
  3. Re-roda o backfill completo

Uso:
  # Passo 1: Diagnóstico (dry-run)
  python scripts/run_flashscore_rescrape.py --step cleanup --dry-run

  # Passo 2: Deletar e resetar
  python scripts/run_flashscore_rescrape.py --step cleanup

  # Passo 3: Re-coletar (executar quantas vezes for preciso até esvaziar)
  xvfb-run python scripts/run_flashscore_rescrape.py --step rescrape --limit 500 --timeout-hours 3

  # Ou tudo de uma vez:
  xvfb-run python scripts/run_flashscore_rescrape.py --step all --limit 500
"""
import asyncio
import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import asyncpg

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from src.db.logger import configure_logging, get_logger

load_dotenv()
configure_logging()
logger = get_logger("run_flashscore_rescrape")


async def init_db():
    return await asyncpg.create_pool(
        user=os.getenv("DB_USER", "admin"),
        password=os.getenv("DB_PASS", "admin_password"),
        database=os.getenv("DB_NAME", "postgres"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )


async def step_cleanup(pool, dry_run: bool = False):
    """
    Deleta TODAS as odds AH e OU com source='flashscore' e reseta os flags.
    Os flashscore_id ficam intactos na tabela matches.
    """
    async with pool.acquire() as conn:
        # ============ DIAGNÓSTICO ============
        print("\n" + "=" * 60)
        print("  DIAGNÓSTICO ANTES DA LIMPEZA")
        print("=" * 60)

        # Total de odds por mercado e fonte
        stats = await conn.fetch("""
            SELECT source, market_type, count(*) as qty
            FROM odds_history
            WHERE source = 'flashscore'
            GROUP BY source, market_type
            ORDER BY market_type
        """)
        print(f"\n  Odds Flashscore por mercado:")
        for s in stats:
            print(f"    {s['market_type']:>6}: {s['qty']:>8} registros")

        # Odds AH e OU que serão deletadas
        ah_count = await conn.fetchval(
            "SELECT count(*) FROM odds_history WHERE source = 'flashscore' AND market_type = 'ah'"
        )
        ou_count = await conn.fetchval(
            "SELECT count(*) FROM odds_history WHERE source = 'flashscore' AND market_type = 'ou'"
        )
        total_delete = ah_count + ou_count

        print(f"\n  SERÃO DELETADAS:")
        print(f"    AH: {ah_count:>8} registros")
        print(f"    OU: {ou_count:>8} registros")
        print(f"    --  {total_delete:>8} TOTAL")

        # Odds que NÃO serão afetadas
        kept = await conn.fetch("""
            SELECT market_type, count(*) as qty
            FROM odds_history
            WHERE source = 'flashscore' AND market_type NOT IN ('ah', 'ou')
            GROUP BY market_type
            ORDER BY market_type
        """)
        if kept:
            print(f"\n  PRESERVADAS (não afetadas):")
            for k in kept:
                print(f"    {k['market_type']:>6}: {k['qty']:>8} registros")

        # Partidas com flag
        scraped_count = await conn.fetchval(
            "SELECT count(*) FROM matches WHERE scraping_flashscore = true"
        )
        total_with_fsid = await conn.fetchval(
            "SELECT count(*) FROM matches WHERE flashscore_id IS NOT NULL"
        )
        print(f"\n  Partidas com flashscore_id (links preservados): {total_with_fsid}")
        print(f"  Partidas com scraping_flashscore = true:         {scraped_count}")

        # Prematch odds (tabela separada)
        try:
            prematch_ah = await conn.fetchval(
                "SELECT count(*) FROM prematch_odds WHERE source = 'flashscore' AND market_type = 'ah'"
            )
            prematch_ou = await conn.fetchval(
                "SELECT count(*) FROM prematch_odds WHERE source = 'flashscore' AND market_type = 'ou'"
            )
            if prematch_ah + prematch_ou > 0:
                print(f"\n  Prematch odds (também serão deletadas):")
                print(f"    AH: {prematch_ah:>8}")
                print(f"    OU: {prematch_ou:>8}")
        except Exception:
            prematch_ah = prematch_ou = 0

        if dry_run:
            print(f"\n  [DRY-RUN] Nenhuma alteração será feita.")
            print(f"  Para executar: remova --dry-run")
            return

        # ============ EXECUTAR ============
        print(f"\n{'=' * 60}")
        print(f"  EXECUTANDO LIMPEZA")
        print(f"{'=' * 60}")

        # 1. Deletar odds AH e OU do Flashscore
        await conn.execute("""
            DELETE FROM odds_history
            WHERE source = 'flashscore' AND market_type IN ('ah', 'ou')
        """)
        print(f"  ✓ Deletadas {total_delete} odds AH/OU da odds_history")

        # 2. Deletar prematch AH e OU se existir
        if prematch_ah + prematch_ou > 0:
            try:
                await conn.execute("""
                    DELETE FROM prematch_odds
                    WHERE source = 'flashscore' AND market_type IN ('ah', 'ou')
                """)
                print(f"  ✓ Deletadas {prematch_ah + prematch_ou} odds AH/OU da prematch_odds")
            except Exception:
                pass

        # 3. Resetar flag scraping_flashscore
        await conn.execute(
            "UPDATE matches SET scraping_flashscore = false WHERE scraping_flashscore = true"
        )
        print(f"  ✓ Flag scraping_flashscore resetado para {scraped_count} partidas")

        # 4. Verificação pós-limpeza
        remaining = await conn.fetchval(
            "SELECT count(*) FROM odds_history WHERE source = 'flashscore' AND market_type IN ('ah', 'ou')"
        )
        print(f"\n  Verificação: odds AH/OU restantes = {remaining}")
        print(f"  flashscore_id preservados = {total_with_fsid}")
        print(f"\n  LIMPEZA CONCLUÍDA! Próximo: --step rescrape")


async def step_rescrape(pool, limit: int, timeout_hours: float):
    """
    Re-coleta odds de todas as partidas (parser corrigido captura tudo).
    """
    from camoufox.async_api import AsyncCamoufox
    from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector
    from src.alerts.telegram_mini import TelegramAlert
    await TelegramAlert.init()

    async with pool.acquire() as conn:
        matches = await conn.fetch("""
            SELECT m.match_id, m.flashscore_id, m.kickoff, l.code
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.status = 'finished'
              AND m.flashscore_id IS NOT NULL
              AND (m.scraping_flashscore IS NULL OR m.scraping_flashscore = false)
            ORDER BY m.kickoff DESC
            LIMIT $1
        """, limit)

    if not matches:
        print("\n[Rescrape] Fila vazia! Todas as partidas já foram re-coletadas.")
        TelegramAlert.fire("info", "📭 Rescrape Flashscore: fila vazia.")
        await asyncio.sleep(1)
        await TelegramAlert.close()
        return

    print(f"\n{'=' * 60}")
    print(f"  RESCRAPE: {len(matches)} partidas a processar")
    print(f"  Timeout: {timeout_hours}h | Limit: {limit}")
    print(f"{'=' * 60}")

    collector = FlashscoreOddsCollector()

    async with AsyncCamoufox(
        headless=False,
        enable_cache=True
    ) as browser:
        total_collected = 0
        total_errors = 0
        total_odds = 0
        start_time = datetime.now()
        max_duration = timedelta(hours=timeout_hours)

        for idx, m in enumerate(matches):
            if datetime.now() - start_time > max_duration:
                print(f"\n[TIMEOUT] {timeout_hours}h atingido. Continuará na próxima execução.")
                break

            match_uuid = m["match_id"]
            fs_id = m["flashscore_id"]
            league = m.get("code", "?")

            print(f"==> [{league}] {idx+1}/{len(matches)}: {fs_id}")

            try:
                async with pool.acquire() as conn:
                    inserted = await collector.collect_match(
                        browser, conn,
                        str(match_uuid), fs_id,
                        is_closing=True,
                        job_id="rescrape_fix_ah_ou"
                    )
                    print(f"    -> {inserted} odds inseridas")
                    total_odds += inserted

                    await conn.execute(
                        "UPDATE matches SET scraping_flashscore = true WHERE match_id = $1",
                        match_uuid
                    )
                    total_collected += 1

            except Exception as e:
                print(f"[ERROR] {fs_id}: {e}")
                total_errors += 1

            await asyncio.sleep(3)

        elapsed = datetime.now() - start_time
        remaining = len(matches) - idx - 1

        print(f"\n{'=' * 60}")
        print(f"  RESUMO RESCRAPE")
        print(f"{'=' * 60}")
        print(f"  Partidas processadas:  {total_collected}")
        print(f"  Odds inseridas:        {total_odds}")
        print(f"  Erros:                 {total_errors}")
        print(f"  Restantes na fila:     {remaining}")
        print(f"  Tempo:                 {elapsed}")

        msg = (
            f"🔄 *Rescrape Flashscore*\n"
            f"Processados: {total_collected}\n"
            f"Odds inseridas: {total_odds}\n"
            f"Erros: {total_errors}\n"
            f"Restantes: {remaining}\n"
            f"Tempo: {elapsed}"
        )
        TelegramAlert.fire("info", msg)

    await asyncio.sleep(1)
    await TelegramAlert.close()


async def main():
    parser = argparse.ArgumentParser(description="Rescrape Flashscore — Contingência AH/OU")
    parser.add_argument("--step", choices=["cleanup", "rescrape", "all"], required=True,
                        help="cleanup: deletar AH/OU + resetar flags | rescrape: re-coletar | all: ambos")
    parser.add_argument("--dry-run", action="store_true",
                        help="Apenas diagnóstico, sem alterar dados")
    parser.add_argument("--limit", type=int, default=500,
                        help="Max partidas por execução (default: 500)")
    parser.add_argument("--timeout-hours", type=float, default=3.0,
                        help="Timeout em horas (default: 3.0)")
    args = parser.parse_args()

    pool = await init_db()

    try:
        if args.step in ("cleanup", "all"):
            await step_cleanup(pool, dry_run=args.dry_run)

        if args.step in ("rescrape", "all") and not args.dry_run:
            await step_rescrape(pool, limit=args.limit, timeout_hours=args.timeout_hours)
    finally:
        await pool.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nRescrape cancelado pelo usuário.")
