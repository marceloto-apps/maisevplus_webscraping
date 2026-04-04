"""Fix direto: para cada match órfão, buscar na API e inserir stats"""
import asyncio
from src.db.pool import get_pool
from src.collectors.footystats.api_client import FootyStatsClient
from src.collectors.footystats.matches_collector import MatchesCollector, parse_kickoff
from src.normalizer.team_resolver import TeamResolver

async def main():
    pool = await get_pool()
    client = FootyStatsClient()
    await TeamResolver.load_cache()
    
    async with pool.acquire() as conn:
        # Buscar todas as seasons das ligas com gap
        seasons = await conn.fetch("""
            SELECT s.footystats_season_id, s.season_id, s.league_id, l.code
            FROM seasons s JOIN leagues l ON l.league_id = s.league_id
            WHERE l.code IN ('ENG_PL', 'SCO_L1', 'NED_ED', 'TUR_SL')
            AND s.footystats_season_id IS NOT NULL
        """)
        
        # Para cada season, buscar dados da API e tentar linkar/inserir stats
        total_fixed = 0
        for season in seasons:
            data = await client.fetch_season_matches(season['footystats_season_id'])
            if not data:
                continue
            
            fixed = 0
            for raw in data:
                fs_id = raw.get('id')
                home_name = str(raw.get('home_name', ''))
                away_name = str(raw.get('away_name', ''))
                
                home_id = await TeamResolver.resolve("footystats", home_name)
                away_id = await TeamResolver.resolve("footystats", away_name)
                if not home_id or not away_id:
                    continue
                
                parsed = MatchesCollector.parse_raw_match(raw)
                kickoff = parsed['matches'].get('kickoff')
                if not kickoff:
                    continue
                
                # Verificar se já tem stats com esse footystats_id
                existing = await conn.fetchval(
                    "SELECT ms.match_id FROM match_stats ms JOIN matches m ON m.match_id = ms.match_id WHERE m.footystats_id = $1 AND ms.source = 'footystats'", 
                    fs_id
                )
                if existing:
                    continue  # Já tem stats
                
                # Procurar o match órfão (sem stats, sem footystats_id)
                match_id = await conn.fetchval("""
                    SELECT m.match_id FROM matches m
                    WHERE m.league_id = $1 AND m.home_team_id = $2 AND m.away_team_id = $3
                    AND ABS(m.kickoff::date - $4::date) <= 1
                    AND m.footystats_id IS NULL
                    AND NOT EXISTS (SELECT 1 FROM match_stats ms WHERE ms.match_id = m.match_id AND ms.source = 'footystats')
                    LIMIT 1
                """, season['league_id'], home_id, away_id, kickoff.date())
                
                if not match_id:
                    continue
                
                # Gravar footystats_id e scores
                m = parsed['matches']
                await conn.execute("""
                    UPDATE matches SET footystats_id = $1, ht_home = $2, ht_away = $3, updated_at = NOW()
                    WHERE match_id = $4
                """, fs_id, m.get('ht_home'), m.get('ht_away'), match_id)
                
                # Inserir stats
                s = parsed['match_stats']
                await conn.execute("""
                    INSERT INTO match_stats (
                        match_id, xg_home, xg_away, total_goals_ft,
                        goals_home_minutes, goals_away_minutes,
                        corners_home_ft, corners_away_ft,
                        offsides_home, offsides_away,
                        yellow_cards_home_ft, yellow_cards_away_ft,
                        red_cards_home_ft, red_cards_away_ft,
                        shots_on_target_home, shots_on_target_away,
                        shots_off_target_home, shots_off_target_away,
                        shots_home, shots_away,
                        fouls_home, fouls_away,
                        possession_home, possession_away,
                        btts_potential,
                        corners_home_ht, corners_away_ht,
                        corners_home_2h, corners_away_2h,
                        goals_home_2h, goals_away_2h,
                        cards_home_ht, cards_away_ht,
                        cards_home_2h, cards_away_2h,
                        dangerous_attacks_home, dangerous_attacks_away,
                        attacks_home, attacks_away,
                        goals_home_0_10_min, goals_away_0_10_min,
                        corners_home_0_10_min, corners_away_0_10_min,
                        cards_home_0_10_min, cards_away_0_10_min,
                        home_ppg, away_ppg,
                        pre_match_home_ppg, pre_match_away_ppg,
                        pre_match_overall_ppg_home, pre_match_overall_ppg_away,
                        xg_prematch_home, xg_prematch_away,
                        source
                    ) VALUES (
                        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                        $11,$12,$13,$14,$15,$16,$17,$18,$19,$20,
                        $21,$22,$23,$24,$25,$26,$27,$28,$29,$30,
                        $31,$32,$33,$34,$35,$36,$37,$38,$39,$40,
                        $41,$42,$43,$44,$45,$46,$47,$48,$49,$50,
                        $51,$52,$53,'footystats'
                    ) ON CONFLICT (match_id, source) DO NOTHING
                """,
                    match_id,
                    s.get('xg_home'), s.get('xg_away'), s.get('total_goals_ft'),
                    s.get('goals_home_minutes'), s.get('goals_away_minutes'),
                    s.get('corners_home_ft'), s.get('corners_away_ft'),
                    s.get('offsides_home'), s.get('offsides_away'),
                    s.get('yellow_cards_home_ft'), s.get('yellow_cards_away_ft'),
                    s.get('red_cards_home_ft'), s.get('red_cards_away_ft'),
                    s.get('shots_on_target_home'), s.get('shots_on_target_away'),
                    s.get('shots_off_target_home'), s.get('shots_off_target_away'),
                    s.get('shots_home'), s.get('shots_away'),
                    s.get('fouls_home'), s.get('fouls_away'),
                    s.get('possession_home'), s.get('possession_away'),
                    s.get('btts_potential'),
                    s.get('corners_home_ht'), s.get('corners_away_ht'),
                    s.get('corners_home_2h'), s.get('corners_away_2h'),
                    s.get('goals_home_2h'), s.get('goals_away_2h'),
                    s.get('cards_home_ht'), s.get('cards_away_ht'),
                    s.get('cards_home_2h'), s.get('cards_away_2h'),
                    s.get('dangerous_attacks_home'), s.get('dangerous_attacks_away'),
                    s.get('attacks_home'), s.get('attacks_away'),
                    s.get('goals_home_0_10_min'), s.get('goals_away_0_10_min'),
                    s.get('corners_home_0_10_min'), s.get('corners_away_0_10_min'),
                    s.get('cards_home_0_10_min'), s.get('cards_away_0_10_min'),
                    s.get('home_ppg'), s.get('away_ppg'),
                    s.get('pre_match_home_ppg'), s.get('pre_match_away_ppg'),
                    s.get('pre_match_overall_ppg_home'), s.get('pre_match_overall_ppg_away'),
                    s.get('xg_prematch_home'), s.get('xg_prematch_away')
                )
                fixed += 1
            
            if fixed:
                print(f"  {season['code']} {season['footystats_season_id']}: +{fixed} stats linkadas")
                total_fixed += fixed
        
        # Resultado
        remaining = await conn.fetchval("""
            SELECT COUNT(*) FROM matches m
            WHERE m.status = 'finished'
            AND NOT EXISTS (SELECT 1 FROM match_stats ms WHERE ms.match_id = m.match_id AND ms.source = 'footystats')
        """)
        print(f"\n✅ Total fixados: {total_fixed}")
        print(f"Gap restante: {remaining}")
    
    await client.close()
    await pool.close()

asyncio.run(main())
