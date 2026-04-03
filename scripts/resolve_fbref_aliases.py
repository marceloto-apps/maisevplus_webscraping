import asyncio
import difflib
import sys
from src.db.pool import get_pool

async def resolve_fbref_aliases():
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # Puxa todos os unknown_aliases que ainda precisam ser resolvidos
        unknowns = await conn.fetch("SELECT id, raw_name, league_code FROM unknown_aliases WHERE source='fbref' AND resolved=FALSE")
        
        if not unknowns:
            print("nenhum alias pendente!")
            return
            
        print(f"[*] Encontrados {len(unknowns)} aliases pendentes de resolução.\n")
        
        # Busca todos os times que a FootyStats Semeou na base (todas as ligas)
        teams = await conn.fetch("""
            SELECT t.team_id, t.name_canonical 
            FROM teams t
        """)
        
        if not teams:
            print(f"[!] Nenhum time oficial encontrado na base.")
            return
            
        team_dict = {t["name_canonical"]: t["team_id"] for t in teams}
        team_names = list(team_dict.keys())
        
        resolvidos = 0
        
        for u in unknowns:
            clean_name = u['raw_name'].replace('-', ' ')
            
            # Tenta o fuzzy match automático com nota bem alta (0.7) evitando sigla cruzada
            matches = difflib.get_close_matches(clean_name, team_names, n=5, cutoff=0.3)
            
            # Auto resolve apenas se a pontuação for muito óbvia (> 0.6)
            auto_resolved = False
            if matches:
                score = difflib.SequenceMatcher(None, clean_name.lower(), matches[0].lower()).ratio()
                if score > 0.6:
                    best = matches[0]
                    tid = team_dict[best]
                    print(f"⚡ [AUTO-MATCH] '{u['raw_name']}' -> '{best}' (Confiança: {score*100:.0f}%)")
                    await conn.execute("INSERT INTO team_aliases (team_id, source, alias_name) VALUES ($1, 'fbref', $2) ON CONFLICT DO NOTHING", tid, u['raw_name'])
                    await conn.execute("UPDATE unknown_aliases SET resolved=TRUE, resolved_team_id=$1, resolved_at=NOW() WHERE id=$2", tid, u['id'])
                    resolvidos += 1
                    auto_resolved = True
            
            if auto_resolved:
                continue
                
            # Se não auto-resolveu (como siglas 'QPR'), joga pro Humano
            print(f"\n❓ [MANUAL] O robô encontrou: '{u['raw_name']}' - Pulando interação manual em background.")
            print("Opções na sua base oficial:")
            for idx, tname in enumerate(team_names, 1):
                # Destaca levemente as sugestões próximas
                if tname in matches:
                    print(f" * {idx:3d} - {tname}")
            print("⏭️  Ignorado.")

    await pool.close()
    print(f"\n🚀 Limpeza Finalizada! Resoluções salvas: {resolvidos}")

if __name__ == "__main__":
    asyncio.run(resolve_fbref_aliases())
