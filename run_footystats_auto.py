"""
Script de Backfill FootyStats com Auto-Resolução de Aliases.

Uso:
    python run_footystats_auto.py ENG_PL          # 1 liga, todas as temporadas
    python run_footystats_auto.py ALL              # todas as ligas
    python run_footystats_auto.py ALL --seasons 2  # todas as ligas, últimas 2 temporadas
"""
import asyncio
import os
import sys
import csv
import argparse
from rapidfuzz import fuzz

from src.db.pool import get_pool
from src.collectors.footystats.api_client import FootyStatsClient
from src.normalizer.team_resolver import TeamResolver
from src.db.logger import get_logger

logger = get_logger(__name__)

# Threshold mínimo para auto-resolução (85% = muito mais conservador que 60%)
ALIAS_THRESHOLD = 85


async def auto_resolve_teams(unresolved_teams_file: str):
    """
    Resolve nomes de times não encontrados usando fuzzy matching.
    Usa token_sort_ratio para ser robusto a inversões de palavras.
    Threshold de 85% para evitar falsos positivos como Newcastle→Carlisle.
    """
    if not os.path.exists(unresolved_teams_file):
        logger.info("Nenhum alias pendente para resolver.")
        return 0

    pool = await get_pool()
    async with pool.acquire() as conn:
        all_teams = await conn.fetch("SELECT team_id, name_canonical FROM teams")
        
        resolved_count = 0
        skipped = []
        
        with open(unresolved_teams_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            
            for row in reader:
                if not row: continue
                raw_name = row[0].strip()
                
                exists = await conn.fetchval(
                    "SELECT 1 FROM team_aliases WHERE source='footystats' AND alias_name=$1",
                    raw_name.lower()
                )
                if exists:
                    continue

                best_match = None
                best_score = 0
                best_canonical = ""
                for t in all_teams:
                    # token_sort_ratio: "Tottenham Hotspur" vs "Hotspur Tottenham" = 100%
                    score = fuzz.token_sort_ratio(raw_name.lower(), t['name_canonical'].lower())
                    if score > best_score:
                        best_score = score
                        best_match = t['team_id']
                        best_canonical = t['name_canonical']

                if best_score >= ALIAS_THRESHOLD and best_match:
                    logger.info(f"✅ Auto-resolvido: {raw_name} → {best_canonical} (ID {best_match}, Score: {best_score:.1f}%)")
                    await conn.execute(
                        "INSERT INTO team_aliases (source, alias_name, team_id) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                        'footystats', raw_name.lower(), best_match
                    )
                    resolved_count += 1
                else:
                    skipped.append((raw_name, best_canonical, best_score))
                    logger.warning(f"⚠️ SKIP: {raw_name} → melhor: {best_canonical} (Score: {best_score:.1f}% < {ALIAS_THRESHOLD}%)")

        if skipped:
            logger.warning(f"Total de {len(skipped)} times NÃO resolvidos (requerem revisão manual)")

    return resolved_count


async def run_pipeline(league_code: str, max_seasons: int = 0):
    """
    Pipeline completo: coleta → auto-resolve aliases → re-coleta.
    
    Args:
        league_code: código da liga (ex: 'ENG_PL') ou 'ALL' para todas
        max_seasons: limitar a N temporadas mais recentes (0 = todas)
    """
    logger.info(f"🚀 Iniciando Pipeline FootyStats: {league_code} (seasons: {'todas' if max_seasons == 0 else max_seasons})")
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        if league_code == "ALL":
            seasons = await conn.fetch("""
                SELECT s.season_id, s.league_id, s.footystats_season_id, s.label
                FROM seasons s
                WHERE s.footystats_season_id IS NOT NULL
                ORDER BY s.label DESC
            """)
        else:
            seasons = await conn.fetch("""
                SELECT s.season_id, s.league_id, s.footystats_season_id, s.label
                FROM seasons s
                JOIN leagues l ON s.league_id = l.league_id
                WHERE s.footystats_season_id IS NOT NULL
                  AND l.code = $1
                ORDER BY s.label DESC
            """, league_code)

    if not seasons:
        logger.error(f"Nenhuma season encontrada para {league_code}")
        return

    # Filtrar por N temporadas mais recentes (por liga)
    if max_seasons > 0:
        # Agrupar por liga e pegar as N mais recentes de cada
        from collections import defaultdict
        by_league = defaultdict(list)
        for s in seasons:
            by_league[s['league_id']].append(s)
        
        filtered = []
        for league_id, league_seasons in by_league.items():
            # Já estão ordenadas DESC, pegar as primeiras N
            filtered.extend(league_seasons[:max_seasons])
        seasons = filtered

    logger.info(f"📊 Total de seasons a processar: {len(seasons)}")

    from src.collectors.footystats.backfill import FootyStatsBackfill
    client = FootyStatsClient()
    
    output_file = "output/footystats_unresolved_teams.csv"

    async def run_backfill(custom_seasons):
        backfill = FootyStatsBackfill(client)
        await backfill._init_db()
        await TeamResolver.load_cache()
        
        for i, season in enumerate(custom_seasons, 1):
            fs_id = season['footystats_season_id']
            logger.info(f"  [{i}/{len(custom_seasons)}] Season {season.get('label', '?')} (fs_id={fs_id})")
            data = await backfill.api_client.fetch_season_matches(fs_id)
            if data:
                await backfill._process_matches_batch(data, season)
            await asyncio.sleep(0.5)
            
        if backfill.unresolved_teams:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["raw_name"])
                for team in sorted(list(backfill.unresolved_teams)):
                    writer.writerow([team])
        
        return len(backfill.unresolved_teams)

    # Rodada 1: Coleta + descoberta de aliases desconhecidos
    logger.info("═══ FASE 1: Coleta inicial + descoberta de aliases ═══")
    unresolved = await run_backfill(seasons)
    
    # Auto-resolução de aliases
    if unresolved > 0:
        logger.info(f"═══ FASE 2: Auto-resolução de {unresolved} aliases ═══")
        resolved = await auto_resolve_teams(output_file)
        
        # Rodada 2: Re-processar com aliases novos
        if resolved > 0:
            logger.info(f"═══ FASE 3: Re-processamento com {resolved} aliases resolvidos ═══")
            await run_backfill(seasons)
        else:
            logger.info("Nenhum alias resolvido automaticamente. Verifique o CSV para resolução manual.")
    else:
        logger.info("✅ Todos os times foram resolvidos! Sem pendências.")

    await client.close()
    await pool.close()
    logger.info("🏁 Pipeline concluído!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FootyStats Backfill Pipeline")
    parser.add_argument("league", nargs="?", default="ALL", help="Código da liga (ex: ENG_PL) ou ALL")
    parser.add_argument("--seasons", type=int, default=0, help="Limitar a N temporadas mais recentes por liga (0=todas)")
    args = parser.parse_args()
    
    asyncio.run(run_pipeline(args.league, args.seasons))
