"""
scripts/run_flashscore_scheduled_cleaner_bulk.py

Script manual pontual para limpar partidas em massa que ficaram presas no status 'scheduled' no passado.
Acessa as páginas de detalhes via Camoufox e atualiza status e placares no banco de dados.

Uso:
    # Processar todas as partidas no passado com limit de 100
    xvfb-run -a .venv/bin/python scripts/run_flashscore_scheduled_cleaner_bulk.py --limit 100 --all-past

    # Processar partidas dos últimos 30 dias com rotação de browser a cada 30 jogos
    xvfb-run -a .venv/bin/python scripts/run_flashscore_scheduled_cleaner_bulk.py --days-back 30 --batch-size 30
"""
import asyncio
import os
import sys
import argparse
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Garantir que o diretório raiz esteja no path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from src.db.pool import get_pool
from src.db.logger import configure_logging, get_logger
from camoufox.async_api import AsyncCamoufox
from scripts.run_flashscore_scheduled_cleaner import clean_match

configure_logging()
logger = get_logger("scheduled_cleaner_bulk")

async def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Flashscore Scheduled Cleaner - Bulk Mode")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limite de partidas para processar nesta execução."
    )
    parser.add_argument(
        "--batch-size", type=int, default=50,
        help="Quantidade de partidas por lote (antes de rotacionar a instância do browser)."
    )
    parser.add_argument(
        "--days-back", type=int, default=None,
        help="Quantidade de dias para olhar para trás no kickoff."
    )
    parser.add_argument(
        "--all-past", action="store_true", default=False,
        help="Se ativado, seleciona todas as partidas no passado sem restrição de dias."
    )
    parser.add_argument(
        "--headless", action="store_true", default=True,
        help="Executar navegador em modo headless (padrão: True)."
    )
    args = parser.parse_args()

    # Validação mínima de filtros de data
    if not args.all_past and args.days_back is None:
        print("[ERRO] Você precisa especificar --all-past ou --days-back <n_dias> para segurança.")
        return

    pool = await get_pool()
    
    # 1. Montar a Query de seleção com base nos argumentos
    query_parts = [
        """
        SELECT m.match_id, m.flashscore_id, m.kickoff,
               th.name_canonical as home_team, ta.name_canonical as away_team
        FROM matches m
        JOIN teams th ON m.home_team_id = th.team_id
        JOIN teams ta ON m.away_team_id = ta.team_id
        WHERE m.status = 'scheduled'
          AND m.flashscore_id IS NOT NULL
        """
    ]
    
    params = []
    
    if args.all_past:
        # Apenas partidas com pelo menos 3 horas de passado
        query_parts.append("AND m.kickoff < NOW() - INTERVAL '3 hours'")
    elif args.days_back is not None:
        # Partidas entre X dias atrás e 3 horas atrás
        query_parts.append("AND m.kickoff >= NOW() - $1::interval AND m.kickoff < NOW() - INTERVAL '3 hours'")
        params.append(f"{args.days_back} days")

    query_parts.append("ORDER BY m.kickoff DESC") # Começa pelas mais recentes

    if args.limit is not None:
        if len(params) == 0:
            query_parts.append("LIMIT $1")
            params.append(args.limit)
        else:
            query_parts.append("LIMIT $2")
            params.append(args.limit)

    full_query = "\n".join(query_parts)
    
    async with pool.acquire() as conn:
        print("Buscando partidas no banco de dados...")
        rows = await conn.fetch(full_query, *params)
        
    if not rows:
        print("Nenhuma partida pendente encontrada com os critérios definidos.")
        await pool.close()
        return

    total_matches = len(rows)
    print(f"\n[OK] Encontradas {total_matches} partidas elegíveis para limpeza em massa.")
    
    # Converter para dicionários
    matches_list = [dict(r) for r in rows]
    
    # Dividir em lotes para evitar vazamento de memória do navegador
    batch_size = args.batch_size
    batches = [matches_list[i:i + batch_size] for i in range(0, len(matches_list), batch_size)]
    
    updated_counts = {"finished": 0, "postponed": 0, "cancelled": 0, "ignored": 0}
    processed_count = 0
    
    print(f"Dividido em {len(batches)} lotes de tamanho máximo {batch_size}.\n")

    try:
        for b_idx, batch in enumerate(batches):
            print(f"=== Iniciando Lote {b_idx + 1}/{len(batches)} (Tamanho: {len(batch)}) ===")
            
            # Inicializa Camoufox para este lote
            async with AsyncCamoufox(headless=args.headless, os="linux") as browser:
                context = await browser.new_context(
                    timezone_id="America/Sao_Paulo",
                    locale="pt-BR"
                )
                page = await context.new_page()
                
                for idx, r in enumerate(batch):
                    processed_count += 1
                    print(f"[{processed_count}/{total_matches}] Processando: {r['home_team']} vs {r['away_team']} (FS: {r['flashscore_id']})")
                    
                    async with pool.acquire() as conn:
                        try:
                            # Reutiliza a lógica existente de extração e gravação do script diário
                            res = await clean_match(
                                conn, page, r["match_id"], r["flashscore_id"],
                                r["home_team"], r["away_team"], r["kickoff"]
                            )
                            
                            if res in updated_counts:
                                updated_counts[res] += 1
                                print(f"  -> Resultado: {res.upper()}")
                            else:
                                updated_counts["ignored"] += 1
                                print("  -> Resultado: IGNORADO/INCONCLUSIVO")
                                
                        except Exception as e:
                            logger.error(f"Erro ao limpar partida {r['flashscore_id']}: {e}")
                            updated_counts["ignored"] += 1
                            print(f"  -> ERRO: {e}")

                    # Delay anti-bloqueio entre requisições
                    await asyncio.sleep(2.5)

                await page.close()
                await context.close()

            print(f"=== Lote {b_idx + 1} finalizado. Browser rotacionado. ===\n")
            
    except KeyboardInterrupt:
        print("\n[WARN] Execução interrompida pelo usuário.")
    finally:
        total_updated = updated_counts["finished"] + updated_counts["postponed"] + updated_counts["cancelled"]
        print("================ SUMMARY ================")
        print(f"Total avaliado: {processed_count}/{total_matches}")
        print(f"• Atualizados para Finalizados: {updated_counts['finished']}")
        print(f"• Atualizados para Adiados: {updated_counts['postponed']}")
        print(f"• Atualizados para Cancelados: {updated_counts['cancelled']}")
        print(f"• Ignorados/Inconclusivos: {updated_counts['ignored']}")
        print(f"Total de atualizações no banco de dados: {total_updated}")
        print("=========================================")
        
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
