"""Scan completo TODAS as ligas + exportar aliases existentes"""
import asyncio
from src.db.pool import get_pool
from src.collectors.footystats.api_client import FootyStatsClient
from src.normalizer.team_resolver import TeamResolver

async def main():
    pool = await get_pool()
    client = FootyStatsClient()
    await TeamResolver.load_cache()
    
    async with pool.acquire() as conn:
        seasons = await conn.fetch("""
            SELECT s.footystats_season_id, l.code, s.label
            FROM seasons s JOIN leagues l ON l.league_id = s.league_id
            WHERE s.footystats_season_id IS NOT NULL
            ORDER BY l.code, s.label
        """)
        
        # 1. Exportar aliases existentes
        aliases = await conn.fetch("""
            SELECT ta.source, ta.alias_name, t.name_canonical, t.team_id
            FROM team_aliases ta
            JOIN teams t ON t.team_id = ta.team_id
            WHERE ta.source = 'footystats'
            ORDER BY ta.alias_name
        """)
        
        with open('output/footystats_aliases_current.csv', 'w', encoding='utf-8') as f:
            f.write("alias_name,canonical_name,team_id\n")
            for a in aliases:
                f.write(f"{a['alias_name']},{a['name_canonical']},{a['team_id']}\n")
        print(f"✅ Aliases existentes exportados: output/footystats_aliases_current.csv ({len(aliases)} aliases)")
    
    # 2. Scan TODAS as ligas
    unresolved = set()
    total_seasons = len(seasons)
    for i, season in enumerate(seasons, 1):
        if i % 20 == 0:
            print(f"  Escaneando {i}/{total_seasons}...")
        data = await client.fetch_season_matches(season['footystats_season_id'])
        if not data:
            continue
        for raw in data:
            home = str(raw.get('home_name', ''))
            away = str(raw.get('away_name', ''))
            if await TeamResolver.resolve("footystats", home) is None:
                unresolved.add((season['code'], home))
            if await TeamResolver.resolve("footystats", away) is None:
                unresolved.add((season['code'], away))
    
    # Agrupar por liga
    by_league = {}
    for code, name in sorted(unresolved):
        by_league.setdefault(code, []).append(name)
    
    # Exportar CSV para resolução manual
    with open('output/unresolved_ALL.csv', 'w', encoding='utf-8') as f:
        f.write("footystats_name,league,canonical_name\n")
        for code, names in sorted(by_league.items()):
            for n in sorted(set(names)):
                f.write(f"{n},{code},\n")
    
    total = sum(len(v) for v in by_league.values())
    print(f"\n{'='*60}")
    print(f"TIMES SEM ALIAS — SCAN COMPLETO ({total} total)")
    print(f"{'='*60}")
    for code, names in sorted(by_league.items()):
        unique = sorted(set(names))
        print(f"  {code} ({len(unique)} times): {', '.join(unique[:5])}{'...' if len(unique)>5 else ''}")
    
    print(f"\n✅ CSV completo: output/unresolved_ALL.csv")
    
    await client.close()
    await pool.close()

asyncio.run(main())
