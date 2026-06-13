import asyncio
import os
import sys
from datetime import date
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

WINTER_LEAGUES = [
    "AUS_AL", "AUT_L2", "BEL_CPL", "NED_ED2", "POR_L2", "SWI_CL", 
    "SAU_D1", "BUL_PL", "CRO_HNL", "DEN_SL", "EGY_PL", "HUN_N1", 
    "ISR_LHA", "POL_EK", "ROM_SL", "SRB_SL"
]

ALL_NEW_LEAGUES = [
    "IRL_D1", "ARG_PN", "AUS_AL", "AUT_L2", "BEL_CPL", "NED_ED2", "POR_L2", "SWI_CL",
    "SAU_D1", "BUL_PL", "CRO_HNL", "DEN_SL", "EGY_PL", "HUN_N1", "ISL_BDK", "ISR_LHA",
    "POL_EK", "ROM_SL", "SRB_SL"
]

async def main():
    load_dotenv()
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # Iniciamos uma transação para garantir atomicidade
        async with conn.transaction():
            print("=== INICIANDO AJUSTE DE TEMPORADAS E MIGACOES ===")
            
            # 1. Cadastrar Temporada 2026/2027 e ajustar is_current para as Ligas de Inverno
            for code in WINTER_LEAGUES:
                # Obter o league_id
                league = await conn.fetchrow("SELECT league_id FROM leagues WHERE code = $1", code)
                if not league:
                    print(f"[WARN] Liga {code} nao encontrada no banco!")
                    continue
                league_id = league["league_id"]
                
                # Inserir ou atualizar 2026/2027
                # Como é inverno, começa em 2026-08-01 e vai até 2027-05-31
                season_26_27_id = await conn.fetchval("""
                    INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, is_current)
                    VALUES ($1, '2026/2027', $2, $3, 0, TRUE)
                    ON CONFLICT (league_id, label) DO UPDATE SET is_current = TRUE
                    RETURNING season_id;
                """, league_id, date(2026, 8, 1), date(2027, 5, 31))
                
                print(f"Liga {code} (ID {league_id}): Temporada 2026/2027 registrada/ativada (ID: {season_26_27_id})")
                
                # Desativar is_current de qualquer outra temporada da liga (ex: 2025/2026)
                res = await conn.execute("""
                    UPDATE seasons 
                    SET is_current = FALSE 
                    WHERE league_id = $1 AND label != '2026/2027' AND is_current = TRUE
                """, league_id)
                print(f"   Temporadas anteriores desativadas para {code}. Resultado: {res}")
                
                # 2. Migrar partidas futuras erroneamente salvas sob 2025/2026
                # Buscar o ID de 2025/2026
                season_25_26_id = await conn.fetchval("""
                    SELECT season_id FROM seasons WHERE league_id = $1 AND label = '2025/2026'
                """, league_id)
                
                if season_25_26_id:
                    # Mover partidas com kickoff pós 2026-06-01 de 2025/2026 para 2026/2027
                    migrated = await conn.fetchval("""
                        WITH updated AS (
                            UPDATE matches
                            SET season_id = $1
                            WHERE season_id = $2 AND kickoff >= '2026-06-01'
                            RETURNING match_id
                        )
                        SELECT COUNT(*) FROM updated;
                    """, season_26_27_id, season_25_26_id)
                    
                    if migrated > 0:
                        print(f"   [MIGRATED] {migrated} partidas futuras movidas de 2025/2026 (ID {season_25_26_id}) para 2026/2027 (ID {season_26_27_id})")
                    else:
                        print(f"   Nenhuma partida futura para migrar em {code}.")
                else:
                    print(f"   Temporada 2025/2026 nao encontrada para {code}.")

            # 3. Resetar o status de discovery (last_discovery_at = NULL) para as temporadas históricas das 19 novas ligas
            print("\n=== RESETANDO STATUS DE DISCOVERY HISTORICO ===")
            for code in ALL_NEW_LEAGUES:
                league = await conn.fetchrow("SELECT league_id FROM leagues WHERE code = $1", code)
                if not league:
                    continue
                league_id = league["league_id"]
                
                # Resetar last_discovery_at das temporadas históricas (is_current = False)
                res = await conn.execute("""
                    UPDATE seasons
                    SET last_discovery_at = NULL
                    WHERE league_id = $1 AND is_current = FALSE
                """, league_id)
                print(f"Discovery resetado para temporadas historicas de {code}. Resultado: {res}")
                
    await pool.close()
    print("\nProcedimento de correcao do banco finalizado com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
