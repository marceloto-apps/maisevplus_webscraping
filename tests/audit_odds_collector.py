"""
tests/audit_odds_collector.py

Harness de auditoria visual e funcional para os 3 jogos selecionados
da Liga Profesional Argentina. Coleta estatísticas (FT+HT+2H) e odds,
e exibe/salva os resultados para validação humana.
"""
import asyncio
import os
import sys
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar diretório de dados do Camoufox
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from camoufox.async_api import AsyncCamoufox
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector, CollectionMetrics
from src.db.pool import get_pool
from src.db.logger import configure_logging, get_logger

load_dotenv()
configure_logging()
logger = get_logger("audit_odds_collector")


async def main():
    print("=" * 80)
    print("  AUDITORIA DE ODDS E ESTATÍSTICAS — LIGA PROFESIONAL ARGENTINA")
    print("=" * 80)

    pool = await get_pool()
    collector = FlashscoreOddsCollector()
    metrics = CollectionMetrics()

    # Cria pasta para armazenar dumps de auditoria
    audit_dir = os.path.join(os.getcwd(), "tests", "audit_output")
    os.makedirs(audit_dir, exist_ok=True)

    async with pool.acquire() as conn:
        # Busca a liga Argentina
        league = await conn.fetchrow("""
            SELECT league_id, name, code, primary_source
            FROM leagues
            WHERE code = 'ARG_LP' OR LOWER(name) LIKE '%liga profesional%'
        """)
        
        if not league:
            print("❌ ERRO: Liga Profesional Argentina (ARG_LP) não encontrada no banco.")
            print("Certifique-se de que a migration 020 rodou e a liga foi cadastrada.")
            return

        print(f"Liga encontrada: {league['name']} [{league['code']}] (Source: {league['primary_source']})")

        # Busca 3 partidas finalizadas com flashscore_id da liga
        matches = await conn.fetch("""
            SELECT m.match_id, m.flashscore_id, m.kickoff,
                   th.name_canonical AS home_team, ta.name_canonical AS away_team
            FROM matches m
            JOIN teams th ON m.home_team_id = th.team_id
            JOIN teams ta ON m.away_team_id = ta.team_id
            WHERE m.league_id = $1
              AND m.status = 'finished'
              AND m.flashscore_id IS NOT NULL
            ORDER BY m.kickoff DESC
            LIMIT 3
        """, league["league_id"])

        if not matches:
            print("❌ ERRO: Nenhuma partida finalizada com flashscore_id encontrada para esta liga.")
            print("Por favor, rode o discovery ou associe flashscore_id manualmente a pelo menos 3 jogos.")
            return

        print(f"Encontrados {len(matches)} jogos para auditoria. Iniciando browser...")

        # Abre browser headed (ou conforme config) para fins de auditoria
        async with AsyncCamoufox(headless=False, enable_cache=True) as browser:
            for idx, match in enumerate(matches):
                match_uuid = match["match_id"]
                fs_id = match["flashscore_id"]
                home = match["home_team"]
                away = match["away_team"]
                kickoff = match["kickoff"]

                print(f"\n👉 [{idx+1}/3] {home} vs {away} (FS ID: {fs_id} | DB ID: {match_uuid})")
                print(f"   Kickoff: {kickoff}")

                # Realiza a coleta de odds e estatísticas
                try:
                    result = await collector.collect_match(
                        browser=browser,
                        conn=conn,
                        match_id_uuid=str(match_uuid),
                        flashscore_id=fs_id,
                        is_closing=True,
                        job_id="audit_test",
                        metrics=metrics,
                        kickoff=kickoff,
                        skip_stats=False
                    )

                    # Busca o que foi persistido na tabela match_stats_fs
                    stats_fs = await conn.fetchrow("""
                        SELECT * FROM match_stats_fs WHERE match_id = $1
                    """, match_uuid)

                    # Busca odds salvas no histórico para este jogo
                    odds_rows = await conn.fetch("""
                        SELECT oh.market_type, oh.period, oh.line, oh.odds_1, oh.odds_x, oh.odds_2,
                               b.name AS bookmaker_name
                        FROM odds_history oh
                        JOIN bookmakers b ON oh.bookmaker_id = b.bookmaker_id
                        WHERE oh.match_id = $1 AND oh.source = 'flashscore'
                        ORDER BY oh.market_type, oh.period, oh.line
                    """, match_uuid)

                    # Salva report do jogo em JSON para auditoria
                    report = {
                        "match_id": str(match_uuid),
                        "flashscore_id": fs_id,
                        "teams": f"{home} vs {away}",
                        "kickoff": str(kickoff),
                        "collector_result": result,
                        "stats_saved_db": dict(stats_fs) if stats_fs else None,
                        "odds_saved_db": [dict(r) for r in odds_rows]
                    }

                    report_path = os.path.join(audit_dir, f"audit_{fs_id}.json")
                    with open(report_path, "w", encoding="utf-8") as f:
                        json.dump(report, f, indent=2, ensure_ascii=False)

                    print(f"   ✅ Coleta e persistência simulada executada sem erros!")
                    print(f"   -> Mercados coletados com sucesso: {result['markets_collected']}")
                    print(f"   -> Mercados falhos: {result['markets_failed']}")
                    print(f"   -> Linhas de stats salvas na DB: {dict(stats_fs) if stats_fs else 'Nenhuma (ou nula)'}")
                    print(f"   -> Quantidade de odds inseridas/encontradas no DB: {len(odds_rows)}")
                    print(f"   -> Relatório detalhado salvo em: {report_path}")

                except Exception as e:
                    print(f"   ❌ ERRO durante a auditoria do jogo {fs_id}: {e}")
                    logger.exception(f"Erro no jogo {fs_id}", exc_info=e)

    await pool.close()
    print("\n" + "=" * 80)
    print("  AUDITORIA CONCLUÍDA! Verifique os arquivos JSON gerados em tests/audit_output/")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
