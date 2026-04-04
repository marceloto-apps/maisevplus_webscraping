import asyncio
import sys
import os

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool
from src.db import helpers

async def main():
    pool = await get_pool()
    
    # Passo 1: Aplicar migration
    print("Aplicando Migration 012_api_football_expansion.sql...")
    with open('migrations/012_api_football_expansion.sql', 'r', encoding='utf-8') as f:
        sql = f.read()
    
    try:
        # asyncpg multi-statement requires processing or execute if it works
        # conn.execute supports multi-statement queries natively
        await helpers.execute(sql)
        print("✓ Migration 012 aplicada com sucesso.")
    except Exception as e:
        print(f"Erro ao aplicar migration: {e}")
        return

    # Passo 2: Atualizar liga BRA_SA
    print("\nAtualizando api_football_league_id para BRA_SA...")
    try:
        update_sql = "UPDATE leagues SET api_football_league_id = 71 WHERE code = 'BRA_SA' RETURNING league_id;"
        res = await helpers.fetch_one(update_sql)
        if res:
            print("✓ Liga BRA_SA atualizada com ID 71.")
        else:
            print("⚠ Liga BRA_SA não encontrada na tabela.")
    except Exception as e:
        print(f"Erro ao atualizar liga: {e}")

    # Verificar banco
    print("\n--- Relatório de Checagem ---")
    val_events = await helpers.fetch_val("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'match_events'")
    val_stats = await helpers.fetch_val("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'match_player_stats'")
    val_col = await helpers.fetch_val("SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'lineups' AND column_name = 'is_home'")
    val_bra = await helpers.fetch_val("SELECT api_football_league_id FROM leagues WHERE code = 'BRA_SA'")
    
    print(f"Tabela match_events criada: {'✅ Sim' if val_events else '❌ Não'}")
    print(f"Tabela match_player_stats criada: {'✅ Sim' if val_stats else '❌ Não'}")
    print(f"Coluna is_home em lineups adicionada: {'✅ Sim' if val_col else '❌ Não'}")
    print(f"BRA_SA api_football_league_id: {val_bra} {'✅' if val_bra == 71 else '❌'}")

if __name__ == "__main__":
    asyncio.run(main())
