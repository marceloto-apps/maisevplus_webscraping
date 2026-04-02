"""
Dry-run controlado da T14.
Usa 1 liga e limita a requests essenciais para checar consistencia E2E.
Roda com: python -m scripts.dry_run_t14
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s")
logger = logging.getLogger("dry_run_t14")

async def main():
    from src.db.pool import close_pool, get_pool
    from src.config.loader import ConfigLoader
    from src.collectors.odds_api.api_collector import OddsApiCollector
    from src.collectors.api_football.api_collector import ApiFootballCollector
    from src.normalizer.team_resolver import TeamResolver
    from src.alerts.telegram_mini import TelegramAlert

    pool = await get_pool()
    await ConfigLoader.load_leagues()
    await TeamResolver.load_cache()
    await TelegramAlert.init()

    logger.info("=" * 60)
    logger.info("DRY-RUN T14 — Validação End-to-End")
    logger.info("=" * 60)

    # ── Teste 1: odds_standard (mode=validation) ──
    logger.info("\n[1/4] odds_standard (validation)...")
    try:
        collector = OddsApiCollector()
        result = await collector.collect(mode="validation")
        logger.info(f"  ✅ Resultado: {result.records_collected} registros processados")
    except Exception as e:
        logger.error(f"  ❌ Falhou: {e}")

    # ── Teste 2: odds_gameday_hourly (mode=prematch) ──
    logger.info("\n[2/4] odds_gameday_hourly (prematch)...")
    try:
        collector = OddsApiCollector()
        result = await collector.collect(mode="prematch")
        logger.info(f"  ✅ Resultado: {result.records_collected} registros processados")
    except Exception as e:
        logger.error(f"  ❌ Falhou: {e}")

    # ── Teste 3: fixtures_weekly ──
    logger.info("\n[3/4] fixtures_weekly...")
    try:
        now = datetime.now(timezone.utc)
        date_from = now.strftime('%Y-%m-%d')
        date_to = (now + timedelta(days=7)).strftime('%Y-%m-%d')
        collector = ApiFootballCollector()
        result = await collector.collect(mode="discovery", date_from=date_from, date_to=date_to)
        logger.info(f"  ✅ Resultado: {result.records_collected} fixtures descobertas")
    except Exception as e:
        logger.error(f"  ❌ Falhou: {e}")

    # ── Teste 4: collect_single (match pontual) ──
    logger.info("\n[4/4] collect_single (sniper)...")
    try:
        async with pool.acquire() as conn:
            # Pega um match real do DB que tenha odds_api_id preenchido num futuro proximo.
            row = await conn.fetchrow("""
                SELECT match_id::text 
                FROM matches 
                WHERE odds_api_id IS NOT NULL 
                  AND kickoff > NOW()
                ORDER BY kickoff ASC 
                LIMIT 1
            """)

        if row:
            match_id = row["match_id"]
            logger.info(f"  Alvo: {match_id}")
            collector = OddsApiCollector()
            result = await collector.collect(mode="single_match", match_id=match_id)
            logger.info(f"  ✅ Resultado: {result.records_collected} odds capturadas")
        else:
            logger.warning("  ⚠️ Nenhum match futuro com odds_api_id no DB")
    except Exception as e:
        logger.error(f"  ❌ Falhou: {e}")

    # ── Resumo ──
    logger.info("\n" + "=" * 60)
    logger.info("DRY-RUN COMPLETO")
    logger.info("=" * 60)

    await TelegramAlert.close()
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
