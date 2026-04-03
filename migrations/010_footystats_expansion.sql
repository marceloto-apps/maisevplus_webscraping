-- Migration 010: FootyStats Fields Expansion
-- Removes misplaced granular fields from matches and expands match_stats with 30+ new columns.

BEGIN;

DROP VIEW IF EXISTS v_match_full;

-- 1. Remover JSONs de timing de matches
ALTER TABLE matches 
DROP COLUMN IF EXISTS goals_home_minutes,
DROP COLUMN IF EXISTS goals_away_minutes;

-- 2. Adicionar as novas colunas à match_stats
ALTER TABLE match_stats
-- Relocated fields
ADD COLUMN IF NOT EXISTS goals_home_minutes jsonb,
ADD COLUMN IF NOT EXISTS goals_away_minutes jsonb,

-- Overall / Game Flow
ADD COLUMN IF NOT EXISTS total_goals_ft smallint,
ADD COLUMN IF NOT EXISTS btts_potential numeric(5,2),

-- Referees / Incidents
ADD COLUMN IF NOT EXISTS offsides_home smallint,
ADD COLUMN IF NOT EXISTS offsides_away smallint,
ADD COLUMN IF NOT EXISTS fouls_home smallint,
ADD COLUMN IF NOT EXISTS fouls_away smallint,

-- 2nd Half Specific (2H)
ADD COLUMN IF NOT EXISTS corners_home_2h smallint,
ADD COLUMN IF NOT EXISTS corners_away_2h smallint,
ADD COLUMN IF NOT EXISTS goals_home_2h smallint,
ADD COLUMN IF NOT EXISTS goals_away_2h smallint,
ADD COLUMN IF NOT EXISTS cards_home_2h smallint,
ADD COLUMN IF NOT EXISTS cards_away_2h smallint,

-- Action Areas (Attacks)
ADD COLUMN IF NOT EXISTS attacks_home smallint,
ADD COLUMN IF NOT EXISTS attacks_away smallint,
ADD COLUMN IF NOT EXISTS dangerous_attacks_home smallint,
ADD COLUMN IF NOT EXISTS dangerous_attacks_away smallint,

-- Early Game (0-10 min)
ADD COLUMN IF NOT EXISTS goals_home_0_10_min smallint,
ADD COLUMN IF NOT EXISTS goals_away_0_10_min smallint,
ADD COLUMN IF NOT EXISTS corners_home_0_10_min smallint,
ADD COLUMN IF NOT EXISTS corners_away_0_10_min smallint,
ADD COLUMN IF NOT EXISTS cards_home_0_10_min smallint,
ADD COLUMN IF NOT EXISTS cards_away_0_10_min smallint,

-- Advanced Metrics (Pre-match e Formatação)
ADD COLUMN IF NOT EXISTS home_ppg numeric(5,2),
ADD COLUMN IF NOT EXISTS away_ppg numeric(5,2),
ADD COLUMN IF NOT EXISTS pre_match_home_ppg numeric(5,2),
ADD COLUMN IF NOT EXISTS pre_match_away_ppg numeric(5,2),
ADD COLUMN IF NOT EXISTS pre_match_overall_ppg_home numeric(5,2),
ADD COLUMN IF NOT EXISTS pre_match_overall_ppg_away numeric(5,2),
ADD COLUMN IF NOT EXISTS xg_prematch_home numeric(5,2),
ADD COLUMN IF NOT EXISTS xg_prematch_away numeric(5,2);


-- ============================================================
-- RECRIAÇÃO DA VIEW (10.3 Match Full)
-- ============================================================
CREATE OR REPLACE VIEW v_match_full AS
SELECT
    m.match_id,
    m.season_id,
    m.kickoff,
    m.status,
    l.code AS league_code,
    l.name AS league_name,
    l.tier,
    l.xg_source AS xg_primary_source,
    s.label AS season_label,
    th.name_canonical AS home_team,
    ta.name_canonical AS away_team,
    m.ft_home,
    m.ft_away,
    m.ht_home,
    m.ht_away,
    fs.goals_home_minutes,   -- <= MOVIDO PARA CÁ
    fs.goals_away_minutes,   -- <= MOVIDO PARA CÁ

    -- xG por fonte
    fs.xg_home AS xg_home_footystats,
    fs.xg_away AS xg_away_footystats,
    us.xg_home AS xg_home_understat,
    us.xg_away AS xg_away_understat,
    fb.xg_home AS xg_home_fbref,
    fb.xg_away AS xg_away_fbref,

    -- xG best: prioridade da liga → fallback cascata
    COALESCE(
        CASE l.xg_source
            WHEN 'understat'  THEN us.xg_home
            WHEN 'fbref'      THEN fb.xg_home
            WHEN 'footystats' THEN fs.xg_home
        END,
        us.xg_home, fb.xg_home, fs.xg_home
    ) AS xg_home_best,
    COALESCE(
        CASE l.xg_source
            WHEN 'understat'  THEN us.xg_away
            WHEN 'fbref'      THEN fb.xg_away
            WHEN 'footystats' THEN fs.xg_away
        END,
        us.xg_away, fb.xg_away, fs.xg_away
    ) AS xg_away_best,

    -- Stats (footystats primário, fbref fallback)
    COALESCE(fs.shots_home, fb.shots_home)                     AS shots_home,
    COALESCE(fs.shots_away, fb.shots_away)                     AS shots_away,
    COALESCE(fs.shots_on_target_home, fb.shots_on_target_home) AS shots_on_target_home,
    COALESCE(fs.shots_on_target_away, fb.shots_on_target_away) AS shots_on_target_away,
    COALESCE(fs.possession_home, fb.possession_home)           AS possession_home,
    COALESCE(fs.possession_away, fb.possession_away)           AS possession_away,
    fs.corners_home_ft,
    fs.corners_away_ft,
    fs.total_corners_ft,
    fs.corners_home_ht,
    fs.corners_away_ht,
    fs.total_corners_ht,
    fs.yellow_cards_home_ft,
    fs.yellow_cards_away_ft,
    fs.red_cards_home_ft,
    fs.red_cards_away_ft,
    fs.cards_home_ht,
    fs.cards_away_ht

FROM matches m
JOIN leagues l  ON l.league_id = m.league_id
JOIN seasons s  ON s.season_id = m.season_id
JOIN teams th   ON th.team_id  = m.home_team_id
JOIN teams ta   ON ta.team_id  = m.away_team_id
LEFT JOIN match_stats fs ON fs.match_id = m.match_id AND fs.source = 'footystats'
LEFT JOIN match_stats us ON us.match_id = m.match_id AND us.source = 'understat'
LEFT JOIN match_stats fb ON fb.match_id = m.match_id AND fb.source = 'fbref';

COMMENT ON VIEW v_match_full IS 'xG de todas as fontes + xg_*_best resolvido por prioridade da liga. Interface principal para M2.';

COMMIT;
