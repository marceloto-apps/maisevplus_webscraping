-- Migration 011: Reestruturação completa da match_stats
-- Recria a tabela com colunas na ordem correta e source/collected_at no final.
-- Limpa aliases incorretos da footystats para re-resolução.

BEGIN;

-- 1. Dropar views dependentes
DROP VIEW IF EXISTS v_match_full CASCADE;

-- 2. Dropar a tabela antiga (vai limpar tudo — TRUNCATE implícito)
DROP TABLE IF EXISTS match_stats CASCADE;

-- 3. Limpar aliases footystats auto-resolvidos (serão re-criados com threshold mais alto)
DELETE FROM team_aliases WHERE source = 'footystats';

-- 4. Recriar tabela com colunas na ordem correta
CREATE TABLE match_stats (
    stat_id                     SERIAL PRIMARY KEY,
    match_id                    UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,

    -- xG
    xg_home                     NUMERIC(5,2),
    xg_away                     NUMERIC(5,2),
    xga_home                    NUMERIC(5,2),  -- futuro: fbref/understat
    xga_away                    NUMERIC(5,2),  -- futuro: fbref/understat

    -- Gols
    total_goals_ft              SMALLINT,
    goals_home_minutes          JSONB,
    goals_away_minutes          JSONB,

    -- Escanteios FT
    corners_home_ft             SMALLINT,
    corners_away_ft             SMALLINT,
    total_corners_ft            SMALLINT GENERATED ALWAYS AS (corners_home_ft + corners_away_ft) STORED,

    -- Impedimentos
    offsides_home               SMALLINT,
    offsides_away               SMALLINT,

    -- Cartões FT
    yellow_cards_home_ft        SMALLINT,
    yellow_cards_away_ft        SMALLINT,
    red_cards_home_ft           SMALLINT,
    red_cards_away_ft           SMALLINT,

    -- Finalizações
    shots_on_target_home        SMALLINT,
    shots_on_target_away        SMALLINT,
    shots_off_target_home       SMALLINT,
    shots_off_target_away       SMALLINT,
    shots_home                  SMALLINT,
    shots_away                  SMALLINT,

    -- Faltas
    fouls_home                  SMALLINT,
    fouls_away                  SMALLINT,

    -- Posse
    possession_home             NUMERIC(4,1),
    possession_away             NUMERIC(4,1),

    -- BTTS
    btts_potential              NUMERIC(5,2),

    -- Escanteios HT
    corners_home_ht             SMALLINT,
    corners_away_ht             SMALLINT,

    -- Escanteios 2H
    corners_home_2h             SMALLINT,
    corners_away_2h             SMALLINT,

    -- Total Escanteios HT (gerado)
    total_corners_ht            SMALLINT GENERATED ALWAYS AS (
        CASE WHEN corners_home_ht IS NOT NULL AND corners_away_ht IS NOT NULL
             THEN corners_home_ht + corners_away_ht
             ELSE NULL END
    ) STORED,

    -- Gols 2H
    goals_home_2h               SMALLINT,
    goals_away_2h               SMALLINT,

    -- Cartões HT
    cards_home_ht               SMALLINT,
    cards_away_ht               SMALLINT,

    -- Cartões 2H
    cards_home_2h               SMALLINT,
    cards_away_2h               SMALLINT,

    -- Ataques
    dangerous_attacks_home      SMALLINT,
    dangerous_attacks_away      SMALLINT,
    attacks_home                SMALLINT,
    attacks_away                SMALLINT,

    -- Primeiros 10 minutos
    goals_home_0_10_min         SMALLINT,
    goals_away_0_10_min         SMALLINT,
    corners_home_0_10_min       SMALLINT,
    corners_away_0_10_min       SMALLINT,
    cards_home_0_10_min         SMALLINT,
    cards_away_0_10_min         SMALLINT,

    -- PPG
    home_ppg                    NUMERIC(5,2),
    away_ppg                    NUMERIC(5,2),
    pre_match_home_ppg          NUMERIC(5,2),
    pre_match_away_ppg          NUMERIC(5,2),
    pre_match_overall_ppg_home  NUMERIC(5,2),
    pre_match_overall_ppg_away  NUMERIC(5,2),

    -- xG Pre-Match
    xg_prematch_home            NUMERIC(5,2),
    xg_prematch_away            NUMERIC(5,2),

    -- ÚLTIMAS COLUNAS (conforme requisito)
    source                      VARCHAR(20) NOT NULL,
    collected_at                TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(match_id, source)
);

COMMENT ON TABLE match_stats IS 'Múltiplas fontes por jogo (footystats + understat/fbref). source e collected_at são as últimas colunas.';


-- 5. Recriar view v_match_full
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
