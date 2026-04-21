-- =============================================================
-- 002_reference_tables.sql
-- Tabelas de referência: leagues, teams, team_aliases,
-- unknown_aliases, seasons, bookmakers, api_keys
-- =============================================================

-- ------------------------------------------------------------
-- 4.1 leagues
-- ------------------------------------------------------------
CREATE TABLE leagues (
    league_id           SERIAL PRIMARY KEY,
    code                VARCHAR(10) UNIQUE NOT NULL,
    name                VARCHAR(100) NOT NULL,
    country             VARCHAR(50) NOT NULL,
    tier                SMALLINT NOT NULL DEFAULT 1,
    season_format       VARCHAR(10) NOT NULL,
    football_data_code  VARCHAR(10),
    football_data_type  VARCHAR(10),
    understat_name      VARCHAR(50),
    fbref_id            VARCHAR(20),
    flashscore_path     VARCHAR(100),
    footystats_name     VARCHAR(100),
    api_football_league_id INTEGER,
    xg_source           VARCHAR(20) DEFAULT 'fbref',
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE leagues IS '26 ligas, 14 países.';
COMMENT ON COLUMN leagues.tier IS '1=Main UK+Top5, 2=Europeias adicionais, 3=Extras';
COMMENT ON COLUMN leagues.football_data_type IS 'main=mmz4281/{season}/{code}.csv | extra=new/{code}.csv';
COMMENT ON COLUMN leagues.xg_source IS 'understat (Top5), fbref (19 ligas), footystats (SCO_L1/L2)';

-- ------------------------------------------------------------
-- 4.2 teams
-- ------------------------------------------------------------
CREATE TABLE teams (
    team_id             SERIAL PRIMARY KEY,
    name_canonical      VARCHAR(100) NOT NULL,
    country             VARCHAR(50),
    api_football_id     INTEGER,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE teams IS 'Nome canônico = referência Bet365. ~580 times.';

-- ------------------------------------------------------------
-- 4.3 team_aliases
-- ------------------------------------------------------------
CREATE TABLE team_aliases (
    alias_id            SERIAL PRIMARY KEY,
    team_id             INTEGER NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    source              VARCHAR(30) NOT NULL,
    alias_name          VARCHAR(100) NOT NULL,
    UNIQUE(source, alias_name)
);

COMMENT ON TABLE team_aliases IS 'Cross-source: nome raw → team_id. ~3.480 aliases.';

-- ------------------------------------------------------------
-- 4.4 unknown_aliases
-- ------------------------------------------------------------
CREATE TABLE unknown_aliases (
    id                  SERIAL PRIMARY KEY,
    source              VARCHAR(30) NOT NULL,
    raw_name            VARCHAR(100) NOT NULL,
    league_code         VARCHAR(10),
    first_seen          TIMESTAMPTZ DEFAULT NOW(),
    resolved            BOOLEAN DEFAULT FALSE,
    resolved_team_id    INTEGER REFERENCES teams(team_id),
    resolved_at         TIMESTAMPTZ,
    UNIQUE(source, raw_name)
);

COMMENT ON TABLE unknown_aliases IS 'Aliases pendentes de revisão manual. Alerta via Telegram.';

-- ------------------------------------------------------------
-- 4.5 seasons
-- ------------------------------------------------------------
CREATE TABLE seasons (
    season_id               SERIAL PRIMARY KEY,
    league_id               INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    label                   VARCHAR(10) NOT NULL,
    start_date              DATE NOT NULL,
    end_date                DATE,
    footystats_season_id    INTEGER NOT NULL,
    football_data_season    VARCHAR(10),
    is_current              BOOLEAN DEFAULT FALSE,
    UNIQUE(league_id, label)
);

COMMENT ON TABLE seasons IS '~131 registros (26 ligas × 5 temporadas + BRA_SA com 6).';

-- ------------------------------------------------------------
-- 4.6 bookmakers
-- ------------------------------------------------------------
CREATE TABLE bookmakers (
    bookmaker_id        SERIAL PRIMARY KEY,
    name                VARCHAR(50) UNIQUE NOT NULL,
    display_name        VARCHAR(50) NOT NULL,
    type                VARCHAR(20) NOT NULL,
    clv_priority        SMALLINT,
    is_active           BOOLEAN DEFAULT TRUE
);

COMMENT ON TABLE bookmakers IS '13 casas. CLV: 1=Pinnacle, 2=Betfair, 3=Bet365.';

-- ------------------------------------------------------------
-- 4.7 api_keys
-- ------------------------------------------------------------
CREATE TABLE api_keys (
    key_id              SERIAL PRIMARY KEY,
    service             VARCHAR(30) NOT NULL,
    key_label           VARCHAR(50) NOT NULL,
    key_value           VARCHAR(200) NOT NULL,
    email               VARCHAR(100),
    usage_today         INTEGER DEFAULT 0,
    usage_month         INTEGER DEFAULT 0,
    limit_daily         INTEGER,
    limit_monthly       INTEGER,
    is_active           BOOLEAN DEFAULT TRUE,
    last_used_at        TIMESTAMPTZ,
    last_reset_at       TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE api_keys IS '7 keys API-Football (100/dia) + 5 keys Odds API (500/mês).';
