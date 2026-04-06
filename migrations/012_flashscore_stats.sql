-- ============================================================
-- Migration: 012_flashscore_stats
-- Data: 2026-04-06
-- Descrição: Adiciona colunas para estatísticas avançadas do Flashscore
-- ============================================================

BEGIN;

-- 1. Adicionar as colunas solicitadas na tabela match_stats
ALTER TABLE match_stats ADD COLUMN IF NOT EXISTS xg_fs_home NUMERIC(5,2);
ALTER TABLE match_stats ADD COLUMN IF NOT EXISTS xg_fs_away NUMERIC(5,2);

ALTER TABLE match_stats ADD COLUMN IF NOT EXISTS xgot_fs_home NUMERIC(5,2);
ALTER TABLE match_stats ADD COLUMN IF NOT EXISTS xgot_fs_away NUMERIC(5,2);

ALTER TABLE match_stats ADD COLUMN IF NOT EXISTS xa_fs_home NUMERIC(5,2);
ALTER TABLE match_stats ADD COLUMN IF NOT EXISTS xa_fs_away NUMERIC(5,2);

ALTER TABLE match_stats ADD COLUMN IF NOT EXISTS crosses_fs_home SMALLINT;
ALTER TABLE match_stats ADD COLUMN IF NOT EXISTS crosses_fs_away SMALLINT;

-- 2. Recriar/Atualizar a view v_match_full para englobar essas colunas
-- A view usava um 'LEFT JOIN fbref'. Faremos o JOIN com flashscore também.

DROP VIEW IF EXISTS v_match_full;

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
    fs.goals_home_minutes,
    fs.goals_away_minutes,

    -- xG das fontes genéricas que usavam colunas originais (footystats, understat, fbref)
    fs.xg_home AS xg_home_footystats,
    fs.xg_away AS xg_away_footystats,
    us.xg_home AS xg_home_understat,
    us.xg_away AS xg_away_understat,
    fb.xg_home AS xg_home_fbref,
    fb.xg_away AS xg_away_fbref,

    -- Flashscore especificas adicionadas agora
    fl.xg_fs_home,
    fl.xg_fs_away,
    fl.xgot_fs_home,
    fl.xgot_fs_away,
    fl.xa_fs_home,
    fl.xa_fs_away,
    fl.crosses_fs_home,
    fl.crosses_fs_away,

    -- xG best: prioridade da liga
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

    -- Outras estatísticas (footystats primário, fbref fallback)
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
LEFT JOIN match_stats fb ON fb.match_id = m.match_id AND fb.source = 'fbref'
LEFT JOIN match_stats fl ON fl.match_id = m.match_id AND fl.source = 'flashscore';

COMMENT ON VIEW v_match_full IS 'xG de todas as fontes (incluindo columns explicitadas de Flashscore). Interface principal para M2.';

COMMIT;
