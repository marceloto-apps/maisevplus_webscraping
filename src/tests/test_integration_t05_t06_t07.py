import pytest
import asyncio
import pandas as pd
from datetime import datetime, timezone

from src.db import get_pool
from src.collectors.football_data.csv_collector import FootballDataCollector
from src.collectors.footystats.backfill import FootyStatsBackfill
from src.collectors.understat.backfill import UnderstatBackfill
from src.normalizer.team_resolver import TeamResolver, MatchResolver

@pytest.mark.asyncio
async def test_full_pipeline_cross_integration():
    """
    Roda os 3 coletores nativos usando Mocks de payloads para atestar que
    as 3 chaves nao duplicam e respeitam o Multi-Source.
    """
    db_pool = await get_pool()
    league_id = None
    team_h = None
    team_a = None

    try:
        # ==========================================
        # SETUP DATA 
        # ==========================================
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM leagues WHERE name = 'TEST_EPL'")
            await conn.execute("DELETE FROM teams WHERE name_canonical IN ('Test Arsenal', 'Test Liverpool')")
            
            league_id = await conn.fetchval("INSERT INTO leagues (code, name, country, tier, season_format) VALUES ('TEST_EPL', 'TEST_EPL', 'England', 1, 'aug_may') RETURNING league_id")
            season_id = await conn.fetchval(
                """INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, football_data_season) 
                   VALUES ($1, '2324', '2023-08-01', '2024-06-01', 99991, '2324') RETURNING season_id""",
                league_id
            )
            team_h = await conn.fetchval("INSERT INTO teams (name_canonical, country) VALUES ('Test Arsenal', 'England') RETURNING team_id")
            team_a = await conn.fetchval("INSERT INTO teams (name_canonical, country) VALUES ('Test Liverpool', 'England') RETURNING team_id")
            
            await conn.execute("""
                INSERT INTO team_aliases (team_id, source, alias_name) VALUES 
                ($1, 'football_data', 'TestArsenal'), ($2, 'football_data', 'TestLiverpool'),
                ($1, 'footystats', 'Test Arsenal FS'), ($2, 'footystats', 'Test Liverpool FS'),
                ($1, 'understat', 'Test Arsenal US'), ($2, 'understat', 'Test Liverpool US')
            """, team_h, team_a)

        # ==========================================
        # 1. T05 - Footbal Data CSV Inject
        # ==========================================
        fd = FootballDataCollector()
        await fd._init_db_and_caches()
        
        fd._pool = db_pool # Injeta pool explicitamente pra evitar recriar e gerar warn
        fd._bookmaker_ids = {'pinnacle': 1, 'bet365': 2}
        fd._league_map['E0_TEST'] = league_id
        fd._season_map[(league_id, '2324')] = season_id
        
        df_mock = pd.DataFrame([{
            'Date': '15/08/2023', 'Time': '12:00',
            'HomeTeam': 'TestArsenal', 'AwayTeam': 'TestLiverpool',
            'FTHG': 2, 'FTAG': 1,
            'PSH': 2.1, 'PSD': 3.4, 'PSA': 3.1
        }])
        
        await fd._insert_matches_and_odds(df_mock, {'type': 'main', 'code': 'E0_TEST', 'fd_season': '2324'})
        
        async with db_pool.acquire() as conn:
            matches = await conn.fetch("SELECT * FROM matches WHERE league_id = $1", league_id)
            assert len(matches) == 1
            assert matches[0]['status'] == 'finished'
            assert matches[0]['kickoff'].hour == 12  # hora default T05

        # ==========================================
        # 2. T06 - Footystats API JSON Inject
        # ==========================================
        fs = FootyStatsBackfill(api_client=None)
        fs._pool = db_pool
        
        team_resolver = TeamResolver(db_pool)
        await team_resolver.load_cache()
        match_resolver = MatchResolver(db_pool, team_resolver)
        
        fs_mock_payload = [{
            'id': 777888, 'status': 'finished',
            'date_unix': int(datetime(2023, 8, 15, 14, 30, tzinfo=timezone.utc).timestamp()),
            'home_name': 'Test Arsenal FS', 'away_name': 'Test Liverpool FS',
            'homeGoalCount': 2, 'awayGoalCount': 1,
            'ht_goals_team_a': 1, 'ht_goals_team_b': 0,
            'team_a_xg': 2.1, 'team_b_xg': 1.1,
            'team_a_corners': 5, 'team_b_corners': 6
        }]
        
        season_stub = {'league_id': league_id, 'season_id': season_id}
        await fs._process_matches_batch(fs_mock_payload, season_stub, match_resolver, team_resolver)
        
        async with db_pool.acquire() as conn:
            matches = await conn.fetch("SELECT * FROM matches WHERE league_id = $1", league_id)
            assert len(matches) == 1  # NAO DUPLICOU!
            assert matches[0]['kickoff'].hour == 14  # Hora atualizada pela FS
            assert matches[0]['ht_home'] == 1 # Atualizou HT
            assert matches[0]['ht_away'] == 0
            
            stats_fs = await conn.fetch("SELECT * FROM match_stats WHERE match_id = $1 AND source = 'footystats'", matches[0]['match_id'])
            assert len(stats_fs) == 1
            assert float(stats_fs[0]['xg_home']) == 2.10

        # ==========================================
        # 3. T07 - Understat Web Scraping Inject
        # ==========================================
        class MockUSScraper:
            async def fetch_match_shots(self, u_id):
                return {
                    'h': [
                        {'minute': 23, 'result': 'Goal', 'xG': 0.82, 'X': 0.9, 'Y': 0.5},
                        {'minute': 55, 'result': 'SavedShot', 'xG': 0.45, 'X': 0.85, 'Y': 0.4},
                        {'minute': 71, 'result': 'Goal', 'xG': 0.68, 'X': 0.88, 'Y': 0.6},
                    ],
                    'a': [
                        {'minute': 38, 'result': 'Goal', 'xG': 0.55, 'X': 0.91, 'Y': 0.45},
                        {'minute': 67, 'result': 'MissedShots', 'xG': 0.12, 'X': 0.75, 'Y': 0.3},
                    ]
                }
                
        us = UnderstatBackfill(scraper=MockUSScraper())
        us._pool = db_pool
        
        us_meta = {
            'id': 999999, 'datetime': '2023-08-15 14:30:00',
            'h': {'title': 'Test Arsenal US'}, 'a': {'title': 'Test Liverpool US'}
        }
        
        # O script de understat vai usar await match_resolver._team_resolver.resolve()
        # Mas o match resolver vai procurar T07.
        await us._process_single_match(0, us_meta, match_resolver, 1)
        
        # ==========================================
        # 4. ASSERTIONS GLOBAIS
        # ==========================================
        async with db_pool.acquire() as conn:
            dupes = await conn.fetch("""
                SELECT league_id, home_team_id, away_team_id, kickoff::date, COUNT(*)
                FROM matches WHERE league_id = $1
                GROUP BY 1, 2, 3, 4 HAVING COUNT(*) > 1
            """, league_id)
            assert len(dupes) == 0, "MATCHES DUPLICADOS!!!"
            
            match_id = matches[0]['match_id']
            source_count = await conn.fetch("SELECT source FROM match_stats WHERE match_id = $1", match_id)
            sources = {r['source'] for r in source_count}
            assert 'footystats' in sources
            assert 'understat' in sources
            assert len(sources) == 2, "ESTRUTURA MULTI-SOURCE QUEBRADA"
            
            fs_xg = await conn.fetchval("SELECT xg_home FROM match_stats WHERE match_id=$1 AND source='footystats'", match_id)
            us_xg = await conn.fetchval("SELECT xg_home FROM match_stats WHERE match_id=$1 AND source='understat'", match_id)
            assert abs(float(fs_xg) - float(us_xg)) < 1.0, f"xG divergiu muito: FS={fs_xg}, US={us_xg}"
            
            raw = await conn.fetchval("SELECT raw_json FROM match_stats WHERE match_id=$1 AND source='understat'", match_id)
            import json
            raw_dict = json.loads(raw) if isinstance(raw, str) else raw
            assert 'aggregated' in raw_dict
            assert 'home_shots' in raw_dict
            assert raw_dict['aggregated']['shots_home'] == 3
            
            # Sub-campos de shots
            for shot in raw_dict['home_shots'] + raw_dict['away_shots']:
                assert all(k in shot for k in ['minute', 'x', 'y', 'xG', 'result']), f"Ddos de shot irregulares: {shot.keys()}"

            # Garantindo a solidez dos Multi-Aliases das 3 rotas
            for tid in [team_h, team_a]:
                aliases = await conn.fetch("SELECT DISTINCT source FROM team_aliases WHERE team_id = $1", tid)
                alias_sources = {r['source'] for r in aliases}
                assert alias_sources >= {'football_data', 'footystats', 'understat'}, f"Timefalha aliases na base: {alias_sources}"

    finally:
        # TEARDOWN CASCATA
        if league_id:
            async with db_pool.acquire() as conn:
                await conn.execute("DELETE FROM match_stats WHERE match_id IN (SELECT match_id FROM matches WHERE league_id = $1)", league_id)
                await conn.execute("DELETE FROM odds_history WHERE match_id IN (SELECT match_id FROM matches WHERE league_id = $1)", league_id)
                await conn.execute("DELETE FROM matches WHERE league_id = $1", league_id)
                await conn.execute("DELETE FROM seasons WHERE league_id = $1", league_id)
                await conn.execute("DELETE FROM leagues WHERE league_id = $1", league_id)
        if team_h and team_a:
            async with db_pool.acquire() as conn:
                await conn.execute("DELETE FROM team_aliases WHERE team_id IN ($1, $2)", team_h, team_a)
                await conn.execute("DELETE FROM teams WHERE team_id IN ($1, $2)", team_h, team_a)
        await db_pool.close()
