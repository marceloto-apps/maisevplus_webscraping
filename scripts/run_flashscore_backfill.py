"""
Backfill / Raspagem em massa para o Flashscore.
Destinado a coletar as partidas do Brasileirão 2026 (status finalizado).
"""
import asyncio
import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv
import asyncpg

# Adiciona o diretório raiz ao PYTHONPATH para permitir imports do módulo src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar diretório de dados do Camoufox ANTES da importação principal
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector
from src.db.logger import configure_logging, get_logger

load_dotenv()
configure_logging()
logger = get_logger("run_flashscore_backfill")

async def init_db():
    return await asyncpg.create_pool(
        user=os.getenv("DB_USER", "admin"),
        password=os.getenv("DB_PASS", "admin_password"),
        database=os.getenv("DB_NAME", "postgres"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

async def mark_match_as_scraped(pool, match_id: str):
    """Marca a partida como coletada para evitar repetição no backfill."""
    async with pool.acquire() as conn:
        try:
            await conn.execute("UPDATE matches SET scraping_flashscore = true WHERE match_id = $1", match_id)
        except asyncpg.exceptions.UndefinedColumnError:
            # Caso a coluna ainda não exista, adiciona em tempo de execução
            await conn.execute("ALTER TABLE matches ADD COLUMN IF NOT EXISTS scraping_flashscore boolean DEFAULT false;")
            await conn.execute("UPDATE matches SET scraping_flashscore = true WHERE match_id = $1", match_id)

async def get_target_matches(pool, limit: int = 50):
    """Busca as partidas do Brasileirão a partir de 2026-01-01."""
    async with pool.acquire() as conn:
        # Tenta se adaptar caso a coluna exista ou não (nós sempre adicionamos dinamicamente acima, mas por garantia):
        try:
            query = """
                SELECT match_id, flashscore_id, kickoff 
                FROM matches 
                WHERE league_id = 71  -- 71 = BRA_SA (Brasileirão Série A)
                  AND date_utc >= '2026-01-01'
                  AND status IN ('FT', 'AET', 'PEN')
                  AND flashscore_id IS NOT NULL
                  AND (scraping_flashscore IS NULL OR scraping_flashscore = false)
                ORDER BY kickoff ASC
                LIMIT $1
            """
            return await conn.fetch(query, limit)
        except asyncpg.exceptions.UndefinedColumnError:
            print("Coluna 'scraping_flashscore' ausente, criando em runtime...")
            await conn.execute("ALTER TABLE matches ADD COLUMN IF NOT EXISTS scraping_flashscore boolean DEFAULT false;")
            # Must re-run the query after altering the table!
            return await conn.fetch(query, limit)

async def main():
    parser = argparse.ArgumentParser(description="Backfill Flashscore BRA_SA 2026")
    parser.add_argument("--limit", type=int, default=380, help="Máximo de partidas para processar")
    args = parser.parse_args()

    pool = await init_db()
    
    matches = await get_target_matches(pool, limit=args.limit)
    if not matches:
        logger.info("[Backfill Flashscore] Nehuma partida nova pendente encontrada no banco para coleta!")
        await pool.close()
        return
        
    logger.info(f"[Backfill Flashscore] {len(matches)} partidas encontradas. Inicializando scraper da Morte...")
    
    collector = FlashscoreOddsCollector()
    
    # Abre o navegador central
    browser = await AsyncCamoufox(
        headless=False,  # Deve rodar sob xvfb-run na VPS
        enable_cache=True,
        window_size=(1920, 1080)
    )
    
    try:
        total_collected = 0
        total_errors = 0
        
        for idx, m in enumerate(matches):
            match_uuid = m["match_id"]
            fs_id = m["flashscore_id"]
            
            logger.info(f"==> Processando {idx+1}/{len(matches)}: Flashscore ID {fs_id} (DB: {match_uuid})")
            
            try:
                # Usamos um novo connection do pool internamente se a função requerer conexão fechada?
                # odds_collector recebe o connection!
                async with pool.acquire() as conn:
                    # Rodamos nossa super função E2E
                    inserted = await collector.collect_match(browser, conn, str(match_uuid), fs_id, is_closing=True, job_id="backfill_bra_2026")
                    
                    logger.info(f"    -> Coleta finalizada para {fs_id}. Odds Inseridas: {inserted}.")
                    
                    # Se não deu crash no meio, marca como processada independentemente do número de registros inseridos 
                    # (já que algumas partidas podem realmente não ter stats).
                    await mark_match_as_scraped(pool, match_uuid)
                    total_collected += 1
                    
            except Exception as e:
                logger.error(f"[ERROR] Falha severa no match {fs_id}. Retrying no futuro. Erro: {e}")
                total_errors += 1
                
            # Random wait para não explodir rate limit ou block da CDN (2 a 4 segundos entre partidas completas)
            await asyncio.sleep(3)
            
        logger.info(f"====== RESUMO BACKFILL ======")
        logger.info(f"Completados com sucesso: {total_collected}")
        logger.info(f"Erros encontrados: {total_errors}")
    
    finally:
        await browser.close()
        await pool.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Backfill cancelado pelo usuário (KeyboardInterrupt).")
