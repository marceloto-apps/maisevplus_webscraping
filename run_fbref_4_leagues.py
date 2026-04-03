import asyncio
import difflib
from pathlib import Path
import yaml

from src.collectors.fbref.backfill import FBRefBackfill
from src.collectors.fbref.api_client import FBRefClient
from src.normalizer.team_resolver import TeamResolver
from src.db.pool import get_pool

async def resolve_aliases(pool):
    print("\n--- INICIANDO RESOLUÇÃO AUTOMÁTICA DE ALIASES ---")
    async with pool.acquire() as conn:
        unknowns = await conn.fetch("SELECT id, raw_name, league_code FROM unknown_aliases WHERE source='fbref' AND resolved=FALSE")
        if not unknowns:
            print("Nenhum alias pendente para resolver.")
            return

        teams = await conn.fetch("SELECT t.team_id, t.name_canonical FROM teams t")
        if not teams: return
            
        team_dict = {t["name_canonical"]: t["team_id"] for t in teams}
        team_names = list(team_dict.keys())
        
        resolvidos = 0
        for u in unknowns:
            clean_name = u['raw_name'].replace('-', ' ')
            matches = difflib.get_close_matches(clean_name, team_names, n=3, cutoff=0.3)
            
            if matches:
                score = difflib.SequenceMatcher(None, clean_name.lower(), matches[0].lower()).ratio()
                if score >= 0.60:
                    best = matches[0]
                    tid = team_dict[best]
                    print(f"[AUTO-MATCH] '{u['raw_name']}' -> '{best}' (Confiança: {score*100:.0f}%)")
                    await conn.execute("INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'fbref', $2) ON CONFLICT DO NOTHING", tid, u['raw_name'])
                    await conn.execute("UPDATE unknown_aliases SET resolved=TRUE, resolved_team_id=$1, resolved_at=NOW() WHERE id=$2", tid, u['id'])
                    resolvidos += 1
                else:
                    print(f"[MANUAL] Necessário mapear humanamente depois: {u['raw_name']} (Melhor palpite: {matches[0]} com {score*100:.0f}%)")
            else:
                print(f"[MANUAL] Nenhum palpite encontrado para: {u['raw_name']}")
    print(f"--- FIM DA RESOLUÇÃO (Salvos: {resolvidos}) ---\n")


async def main():
    pool = await get_pool()
    client = FBRefClient(cooldown=4.0)
    orchestrator = FBRefBackfill(pool, client)
    await orchestrator.init_caches()

    target_leagues = ['BRA_SA', 'MEX_LM', 'AUT_BL', 'SWI_SL']

    config_path = Path("src/config/leagues.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        leagues_config = yaml.safe_load(f).get("leagues", {})

    async with pool.acquire() as conn:
        league_db_mapping = {r['code']: r['league_id'] for r in await conn.fetch("SELECT code, league_id FROM leagues")}

    try:
        print(">> ETAPA 1: Indexando calendário para as 4 Ligas Novas...")
        for code, data in leagues_config.items():
            if code in target_leagues and data.get("xg_source") == "fbref":
                league_id = league_db_mapping.get(code)
                if not league_id: continue
                     
                fbref_id_comp = data.get("fbref_id")
                comp_name_slug = data.get("name").replace(" ", "-")

                for season_key in data.get("seasons", {}):
                    season_label = season_key.replace("/", "-")
                    await orchestrator.index_season(league_id, fbref_id_comp, season_label, comp_name_slug)

        # Salva qualquer time não encontrado
        await TeamResolver.flush_unknowns()

        print(">> ETAPA 2: Auto-Resolvendo Times Desconhecidos...")
        await resolve_aliases(pool)

        print(">> ETAPA 3: Coletando as Estatísticas dos Jogos (Backfill)...")
        # Força o cache do TeamResolver atualizar as novas associações antes de processar
        await TeamResolver.load_cache()
        await orchestrator.process_pending_matches()

        print(">> TODAS AS ETAPAS FORAM CONCLUÍDAS COM SUCESSO! <<")
    except Exception as e:
        print(f"\n[ERRO FATAL] Algo interrompeu o fluxo: {e}")
    finally:
        await client.close()
        await pool.close()
        input("Pressione ENTER para fechar essa janela...")

if __name__ == "__main__":
    import os
    os.system('title FBRef Workflow 4 Leagues')
    asyncio.run(main())
