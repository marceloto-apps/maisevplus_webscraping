-- Migration 025: Inserir e ativar as 18 novas ligas solicitadas para backfill / retrofit

INSERT INTO public.leagues (code, name, country, flashscore_path, primary_source, season_format, tier, is_active)
VALUES
  ('GER_3L',  '3. Liga',             'Germany',              'football/germany/3-liga',             'flashscore', 'aug_may', 3, TRUE),
  ('SAU_SPL', 'Saudi Pro League',    'Saudi Arabia',         'football/saudi-arabia/saudi-pro-league', 'flashscore', 'aug_may', 3, TRUE),
  ('ARG_TF',  'Torneo Federal',      'Argentina',            'football/argentina/torneo-federal',    'flashscore', 'feb_dec', 3, TRUE),
  ('BHR_PL',  'Premier League',      'Bahrain',              'football/bahrain/premier-league',     'flashscore', 'aug_may', 3, TRUE),
  ('BLR_VL',  'Vysshaya Liga',       'Belarus',              'football/belarus/vysshaya-liga',       'flashscore', 'feb_dec', 3, TRUE),
  ('BRA_SC',  'Série C',             'Brazil',               'football/brazil/serie-c',             'flashscore', 'feb_dec', 3, TRUE),
  ('CHI_LDA', 'Liga de Ascenso',     'Chile',                'football/chile/liga-de-ascenso',      'flashscore', 'feb_dec', 3, TRUE),
  ('CHN_L1',  'Jia League',          'China',                'football/china/jia-league',           'flashscore', 'feb_dec', 3, TRUE),
  ('CRO_PNL', 'Prva NL',             'Croatia',              'football/croatia/prva-nl',             'flashscore', 'aug_may', 3, TRUE),
  ('DEN_D1',  '1st Division',        'Denmark',              'football/denmark/1st-division',       'flashscore', 'aug_may', 3, TRUE),
  ('FIN_YKK2','Ykkönen',             'Finland',              'football/finland/ykkonen',            'flashscore', 'feb_dec', 3, TRUE),
  ('FRA_NAT', 'National',            'France',               'football/france/national',            'flashscore', 'aug_may', 3, TRUE),
  ('ISR_LL',  'Leumit League',       'Israel',               'football/israel/leumit-league',       'flashscore', 'aug_may', 3, TRUE),
  ('ITA_SCA', 'Serie C - Group A',   'Italy',                'football/italy/serie-c-group-a',      'flashscore', 'aug_may', 3, TRUE),
  ('ITA_SCB', 'Serie C - Group B',   'Italy',                'football/italy/serie-c-group-b',      'flashscore', 'aug_may', 3, TRUE),
  ('ITA_SCC', 'Serie C - Group C',   'Italy',                'football/italy/serie-c-group-c',      'flashscore', 'aug_may', 3, TRUE),
  ('POL_D1',  'Division 1',          'Poland',               'football/poland/division-1',          'flashscore', 'aug_may', 3, TRUE),
  ('THA_TL1', 'Thai League 1',       'Thailand',             'football/thailand/thai-league-1',     'flashscore', 'aug_may', 3, TRUE)
ON CONFLICT (code) DO UPDATE SET
  flashscore_path = EXCLUDED.flashscore_path,
  primary_source = EXCLUDED.primary_source,
  season_format = EXCLUDED.season_format,
  is_active = TRUE;

-- Adicionar entradas na fila retrofit_queue
INSERT INTO retrofit_queue (league_id, priority, status, total_matches, processed_matches, success_matches, attempts)
SELECT league_id, 999, 'pending', 0, 0, 0, 0
FROM leagues
WHERE code IN (
  'GER_3L', 'SAU_SPL', 'ARG_TF', 'BHR_PL', 'BLR_VL', 'BRA_SC', 'CHI_LDA',
  'CHN_L1', 'CRO_PNL', 'DEN_D1', 'FIN_YKK2', 'FRA_NAT', 'ISR_LL', 'ITA_SCA',
  'ITA_SCB', 'ITA_SCC', 'POL_D1', 'THA_TL1'
)
ON CONFLICT (league_id) DO UPDATE SET
  status = CASE WHEN retrofit_queue.status = 'completed' THEN 'pending' ELSE retrofit_queue.status END;
