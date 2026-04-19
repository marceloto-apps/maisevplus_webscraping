-- =============================================================
-- 003_data_tables.sql
-- Tabelas de dados: matches, match_stats, odds_history
-- (+ hypertable TimescaleDB), lineups
-- Depende de: 002_reference_tables.sql
-- =============================================================

-- ------------------------------------------------------------
-- 5.1 matches
-- ------------------------------------------------------------
CREATE TABLE matches (
    match_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_id           INTEGER NOT NULL REFERENCES seasons(season_id),
    league_id           INTEGER NOT NULL REFERENCES leagues(league_id),
    home_team_id        INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id        INTEGER NOT NULL REFERENCES teams(team_id),
    kickoff             TIMESTAMPTZ NOT NULL,
    matchday            SMALLINT,

    ft_home             SMALLINT,
    ft_away             SMALLINT,
    ht_home             SMALLINT,
    ht_away             SMALLINT,
    goals_home_minutes  JSONB,
    goals_away_minutes  JSONB,

    status              VARCHAR(20) DEFAULT 'scheduled',

    flashscore_id       VARCHAR(30),
    football_data_id    VARCHAR(30),
    fbref_id            VARCHAR(30),
    understat_id        VARCHAR(30),
    footystats_id       INTEGER,
    odds_api_id         VARCHAR(50),
    api_football_id     INTEGER,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_matches_unique_day ON matches (league_id, home_team_id, away_team_id, (kickoff::date));

COMMENT ON TABLE matches IS '~57.500 rows backfill + ~11.500/temporada.';
COMMENT ON COLUMN matches.goals_home_minutes IS '[23, 67, 89]. NULL se sem gols.';
COMMENT ON COLUMN matches.status IS 'scheduled | live | finished | postponed | cancelled';

-- ------------------------------------------------------------
-- 5.2 match_stats
-- ------------------------------------------------------------
CREATE TABLE match_stats (
    stat_id                 SERIAL PRIMARY KEY,
    match_id                UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,

    xg_home                 NUMERIC(5,2),
    xg_away                 NUMERIC(5,2),
    xga_home                NUMERIC(5,2),
    xga_away                NUMERIC(5,2),

    shots_home              SMALLINT,
    shots_away              SMALLINT,
    shots_on_target_home    SMALLINT,
    shots_on_target_away    SMALLINT,
    shots_off_target_home   SMALLINT,
    shots_off_target_away   SMALLINT,

    possession_home         NUMERIC(4,1),
    possession_away         NUMERIC(4,1),

    corners_home_ft         SMALLINT,
    corners_away_ft         SMALLINT,
    total_corners_ft        SMALLINT GENERATED ALWAYS AS (corners_home_ft + corners_away_ft) STORED,

    corners_home_ht         SMALLINT,
    corners_away_ht         SMALLINT,
    total_corners_ht        SMALLINT GENERATED ALWAYS AS (
        CASE WHEN corners_home_ht IS NOT NULL AND corners_away_ht IS NOT NULL
             THEN corners_home_ht + corners_away_ht
             ELSE NULL END
    ) STORED,

    yellow_cards_home_ft    SMALLINT,
    yellow_cards_away_ft    SMALLINT,
    red_cards_home_ft       SMALLINT,
    red_cards_away_ft       SMALLINT,

    cards_home_ht           SMALLINT,
    cards_away_ht           SMALLINT,

    source                  VARCHAR(20) NOT NULL,
    collected_at            TIMESTAMPTZ DEFAULT NOW(),
    raw_json                JSONB,

    UNIQUE(match_id, source)
);

COMMENT ON TABLE match_stats IS 'Múltiplas fontes por jogo (footystats + understat/fbref). FK simples para matches.';

-- ------------------------------------------------------------
-- 5.3 odds_history (TimescaleDB hypertable)
-- ------------------------------------------------------------
CREATE TABLE odds_history (
    time                TIMESTAMPTZ NOT NULL,
    match_id            UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    bookmaker_id        INTEGER NOT NULL REFERENCES bookmakers(bookmaker_id),
    market_type         VARCHAR(10) NOT NULL,
    line                NUMERIC(5,2),
    period              VARCHAR(5) DEFAULT 'ft',

    odds_1              NUMERIC(8,4),
    odds_x              NUMERIC(8,4),
    odds_2              NUMERIC(8,4),

    overround           NUMERIC(6,4),
    is_opening          BOOLEAN DEFAULT FALSE,
    is_closing          BOOLEAN DEFAULT FALSE,

    source              VARCHAR(20) NOT NULL,
    collect_job_id      VARCHAR(50),
    content_hash        CHAR(64) NOT NULL
);

SELECT create_hypertable('odds_history', 'time', chunk_time_interval => INTERVAL '1 month');

COMMENT ON TABLE odds_history IS 'Hypertable TimescaleDB, chunks mensais. >300k rows backfill.';
COMMENT ON COLUMN odds_history.content_hash IS 'SHA-256 para dedup. Igual ao último → skip.';
COMMENT ON COLUMN odds_history.is_closing IS 'Marcado por mark_closing_odds() no job T+2h30.';

-- ------------------------------------------------------------
-- 5.4 lineups
-- ------------------------------------------------------------
CREATE TABLE lineups (
    lineup_id           SERIAL PRIMARY KEY,
    match_id            UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    team_id             INTEGER NOT NULL REFERENCES teams(team_id),
    formation           VARCHAR(10),
    players_json        JSONB NOT NULL,
    source              VARCHAR(20) NOT NULL,
    collected_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(match_id, team_id, source)
);

COMMENT ON TABLE lineups IS 'Escalações via API-Football (T-60min).';
