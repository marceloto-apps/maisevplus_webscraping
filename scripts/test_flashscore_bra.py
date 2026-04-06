"""
scripts/test_flashscore_bra.py
Teste pontual para a liga BRA_SA (Brasileirão).
Executa o Discovery para tentar mapear IDs e em seguida tenta coletar odds
para pelo menos 1 jogo encontrado.
"""
import asyncio
import os
import sys

# Garante que as rotas de importação funcionem rodando da raiz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool, close_pool
from src.normalizer.team_resolver import TeamResolver
from src.config.loader import ConfigLoader
from src.collectors.flashscore.discovery import FlashscoreDiscovery
from src.collectors.flashscore.odds_collector import FlashscoreOddsCollector

async def main():
    print("="*60)
    print("TESTE FLASHSCORE — Liga BRA_SA")
    print("="*60)
    
    # 1. Carregar Dependências do Sistema
    print("\n[1] Inicializando caches do banco de dados...")
    pool = await get_pool()
    await ConfigLoader.load_leagues()
    await TeamResolver.load_cache()
    
    # 2. Executar Discovery (apenas Brasil)
    print("\n[2] Iniciando Discovery para BRA_SA...")
    discovery = FlashscoreDiscovery()
    # Pega fixtures (futuros)
    result_fixtures = await discovery.collect(mode="fixtures", specific_leagues=["BRA_SA"])
    print(f"  -> Fixtures completado. Novos IDs atrelados: {result_fixtures.records_new}")
    
    # Pega results (recentes, para ver se temos matches fáceis)
    result_results = await discovery.collect(mode="results", specific_leagues=["BRA_SA"])
    print(f"  -> Results completado. Novos IDs atrelados: {result_results.records_new}")
    
    # 3. Pegar um match com flashscore_id para o teste de Odds
    print("\n[3] Buscando jogos com ID no banco...")
    async with pool.acquire() as conn:
        matches = await conn.fetch('''
            SELECT m.match_id, m.flashscore_id, l.code
            FROM matches m
            JOIN leagues l ON l.league_id = m.league_id
            WHERE l.code = 'BRA_SA' 
              AND m.flashscore_id IS NOT NULL
            ORDER BY m.kickoff DESC
            LIMIT 3
        ''')
        
    if not matches:
        print("❌ Nenhum jogo da BRA_SA recebeu flashscore_id no banco.")
        print("   Isso geralmente significa que os nomes de times do Flashscore não deram 'match' com nosso banco de dados. Precisamos mapeá-los (aliases).")
        await close_pool()
        return
        
    print(f"✅ Encontrados {len(matches)} jogos da BRA_SA mapeados.\n")
    for m in matches:
        print(f"  - Match: {m['match_id']} | FS_ID: {m['flashscore_id']}")
        
    # Vamos pegar até os 3 e rodar as odds
    targets = [{"match_id": m["match_id"], "flashscore_id": m["flashscore_id"]} for m in matches]
    
    # 4. Coletar Odds
    print("\n[4] Coletando Odds...")
    collector = FlashscoreOddsCollector()
    result_odds = await collector.collect(match_ids=targets)
    
    print("\n" + "="*60)
    if result_odds.status.value == "success":
        print(f"🎉 SUCESSO: Foram coletados/processados {result_odds.records_collected} partidas.")
        print(f"📈 Novas inserts de odds geradas (novas linhas em odds_history): {result_odds.records_new}")
    else:
        print(f"⚠️ PARCIAL/FALHA: Status do job de Odds = {result_odds.status}")
        print(f"   Erros reportados: {result_odds.errors}")
    print("="*60)

    try:
        await TeamResolver.flush_unknowns()
    except:
        pass
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
