"""
scripts/run_flashscore_rescrape.py

Script de contingência para re-capturar odds AH e OU de todas as partidas
já coletadas. Necessário após o fix do parser que corrigiu:
  - Linhas inteiras (0, 1, 2, -3) ignoradas
  - Quarter-goals (-1.25, 2.25) ignoradas  
  - Handicap 0 (célula ausente no DOM) ignorado
  - Odds confundidas com linhas (1.16, 1.57 etc.)

Estratégia:
  1. Limpa odds AH/OU com linhas inválidas (lixo do parser antigo)
  2. Reseta flag scraping_flashscore = false para forçar re-coleta
  3. Re-roda o backfill apenas para os mercados AH e OU
  
Uso:
  # Passo 1: Limpar dados ruins e resetar flags (dry-run)
  python scripts/run_flashscore_rescrape.py --step cleanup --dry-run
  
  # Passo 2: Limpar de verdade
  python scripts/run_flashscore_rescrape.py --step cleanup
  
  # Passo 3: Re-coletar (usa o backfill existente, mas apenas AH e OU)
  python scripts/run_flashscore_rescrape.py --step rescrape --limit 500

  # Ou tudo de uma vez:
  python scripts/run_flashscore_rescrape.py --step all --limit 500
"""
import asyncio
import os
import sys
import argparse
from datetime import datetime, timezone
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
    Passo 1: Remove odds AH/OU com linhas inválidas (lixo do parser antigo)
    e reseta o flag de coleta para forçar re-scrape.
    """
    async with pool.acquire() as conn:
        # 1. Diagnóstico: quantas odds existem por mercado
        print("\n" + "=" * 60)
        print("  DIAGNÓSTICO ATUAL")
        print("=" * 60)

        for mkt in ['1x2', 'ah', 'ou', 'btts']:
            total = await conn.fetchval(
                "SELECT count(*) FROM odds_history WHERE market_type = $1", mkt
            )
            print(f"  {mkt:>6}: {total:>8} registros")
        
        # 2. Identificar odds AH com linhas inválidas (não múltiplo de 0.25)
        invalid_ah = await conn.fetchval("""
            SELECT count(*) FROM odds_history
            WHERE market_type = 'ah'
              AND line IS NOT NULL
              AND MOD(ABS(line) * 100, 25) > 0.01
              AND MOD(ABS(line) * 100, 25) < 24.99
        """)
        print(f"\n  AH com linhas invalidas (nao multiplo 0.25): {invalid_ah}")
        
        # Mostrar exemplos de linhas inválidas
        if invalid_ah > 0:
            examples = await conn.fetch("""
                SELECT DISTINCT line, count(*) as qty
                FROM odds_history
                WHERE market_type = 'ah'
                  AND line IS NOT NULL
                  AND MOD(ABS(line) * 100, 25) > 0.01
                  AND MOD(ABS(line) * 100, 25) < 24.99
                GROUP BY line
                ORDER BY qty DESC
                LIMIT 20
            """)
            print("  Exemplos de linhas invalidas:")
            for ex in examples:
                print(f"    line={ex['line']:>8.2f}  ({ex['qty']} registros)")
        
        # 3. Contar partidas com scraping_flashscore = true
        scraped_count = await conn.fetchval(
            "SELECT count(*) FROM matches WHERE scraping_flashscore = true"
        )
        print(f"\n  Partidas com scraping_flashscore = true: {scraped_count}")

        # 4. Contar quantas partidas têm AH 0 (para verificar pós-fix)
        ah_zero = await conn.fetchval("""
            SELECT count(DISTINCT match_id) FROM odds_history
            WHERE market_type = 'ah' AND line = 0.0
        """)
        print(f"  Partidas com AH 0.0 no banco: {ah_zero}")

        # 5. Contar partidas com OU inteiro
        ou_integer = await conn.fetchval("""
            SELECT count(DISTINCT match_id) FROM odds_history
            WHERE market_type = 'ou' AND line IS NOT NULL AND line = FLOOR(line)
        """)
        print(f"  Partidas com OU inteiro no banco: {ou_integer}")

        if dry_run:
            print(f"\n  [DRY-RUN] Nenhuma alteracao sera feita.")
            print(f"  Para executar de verdade, remova --dry-run")
            return

        # === EXECUTAR LIMPEZA ===
        print(f"\n{'=' * 60}")
        print(f"  EXECUTANDO LIMPEZA")
        print(f"{'=' * 60}")

        # 6. Deletar odds AH com linhas inválidas
        if invalid_ah > 0:
            deleted = await conn.execute("""
                DELETE FROM odds_history
                WHERE market_type = 'ah'
                  AND line IS NOT NULL
                  AND MOD(ABS(line) * 100, 25) > 0.01
                  AND MOD(ABS(line) * 100, 25) < 24.99
            """)
            print(f"  Deletadas {invalid_ah} odds AH com linhas invalidas")
        else:
            print(f"  Nenhuma odd AH invalida encontrada")

        # 7. Resetar flag scraping_flashscore
        result = await conn.execute(
            "UPDATE matches SET scraping_flashscore = false WHERE scraping_flashscore = true"
        )
        print(f"  Flag scraping_flashscore resetado para {scraped_count} partidas")

        print(f"\n  LIMPEZA CONCLUIDA!")
        print(f"  Proximo passo: rodar --step rescrape")


async def step_rescrape(pool, limit: int, timeout_hours: float):
    """
    Passo 2: Re-coleta odds de todas as partidas (agora com parser corrigido).
    Usa o mesmo fluxo do backfill, mas garante coleta de todos os mercados.
    """
    from camoufox.async_api import AsyncCamoufox
    from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector
    from src.alerts.telegram_mini import TelegramAlert
    await TelegramAlert.init()

    async with pool.acquire() as conn:
        # Buscar partidas pendentes (flag resetado)
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
        print("\n[Rescrape] Nenhuma partida pendente! Todas ja foram re-coletadas.")
        TelegramAlert.fire("info", "Rescrape Flashscore: fila vazia, todas as partidas ja re-coletadas.")
        await asyncio.sleep(1)
        await TelegramAlert.close()
        return

    print(f"\n{'=' * 60}")
    print(f"  RESCRAPE: {len(matches)} partidas a processar")
    print(f"  Timeout: {timeout_hours}h")
    print(f"{'=' * 60}")

    collector = FlashscoreOddsCollector()

    async with AsyncCamoufox(
        headless=False,
        enable_cache=True
    ) as browser:
        total_collected = 0
        total_errors = 0
        start_time = datetime.now()
        from datetime import timedelta
        max_duration = timedelta(hours=timeout_hours)

        for idx, m in enumerate(matches):
            if datetime.now() - start_time > max_duration:
                print(f"\n[TIMEOUT] Limite de {timeout_hours}h atingido. Continuará na próxima execução.")
                break

            match_uuid = m["match_id"]
            fs_id = m["flashscore_id"]
            league = m.get("code", "?")

            print(f"==> [{league}] {idx+1}/{len(matches)}: {fs_id} (DB: {match_uuid})")

            try:
                async with pool.acquire() as conn:
                    inserted = await collector.collect_match(
                        browser, conn,
                        str(match_uuid), fs_id,
                        is_closing=True,
                        job_id="rescrape_fix_ah_ou"
                    )
                    print(f"    -> {inserted} odds inseridas")

                    # Marcar como coletado
                    await conn.execute(
                        "UPDATE matches SET scraping_flashscore = true WHERE match_id = $1",
                        match_uuid
                    )
                    total_collected += 1

            except Exception as e:
                print(f"[ERROR] Falha no match {fs_id}: {e}")
                total_errors += 1

            await asyncio.sleep(3)

        elapsed = datetime.now() - start_time
        print(f"\n{'=' * 60}")
        print(f"  RESUMO RESCRAPE")
        print(f"{'=' * 60}")
        print(f"  Coletados com sucesso: {total_collected}")
        print(f"  Erros:                 {total_errors}")
        print(f"  Tempo total:           {elapsed}")
        print(f"  Restantes:             {len(matches) - idx - 1}")

        if total_collected > 0:
            TelegramAlert.fire("info",
                f"🔄 *Rescrape Flashscore Finalizado*\n"
                f"Coletados: {total_collected}\n"
                f"Erros: {total_errors}\n"
                f"Tempo: {elapsed}"
            )

    await asyncio.sleep(1)
    await TelegramAlert.close()


async def main():
    parser = argparse.ArgumentParser(description="Rescrape Flashscore - Contingência AH/OU")
    parser.add_argument("--step", choices=["cleanup", "rescrape", "all"], required=True,
                        help="cleanup: limpar dados ruins e resetar flags | rescrape: re-coletar | all: ambos")
    parser.add_argument("--dry-run", action="store_true", help="Apenas diagnostico, sem alterar dados")
    parser.add_argument("--limit", type=int, default=500, help="Max partidas por execucao (default: 500)")
    parser.add_argument("--timeout-hours", type=float, default=3.0, help="Timeout em horas (default: 3.0)")
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
