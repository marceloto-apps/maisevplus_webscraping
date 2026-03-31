-- =============================================================
-- 006_indexes.sql
-- Criação de indexes consolidados para performance
-- Depende de: 002_reference_tables.sql, 003_data_tables.sql, 004_control_tables.sql
-- =============================================================

-- TEAM ALIASES
CREATE INDEX idx_team_aliases_lookup ON team_aliases(source, alias_name);

-- UNKNOWN ALIASES
CREATE INDEX idx_unknown_aliases_pending ON unknown_aliases(resolved, source) WHERE resolved = FALSE;

-- SEASONS
CREATE INDEX idx_seasons_league ON seasons(league_id);
CREATE INDEX idx_seasons_current ON seasons(is_current) WHERE is_current = TRUE;
CREATE INDEX idx_seasons_footystats ON seasons(footystats_season_id);

-- API KEYS
CREATE INDEX idx_api_keys_service ON api_keys(service, is_active);

-- MATCHES
CREATE INDEX idx_matches_kickoff ON matches(kickoff);
CREATE INDEX idx_matches_league_status ON matches(league_id, status);
CREATE INDEX idx_matches_season ON matches(season_id);
CREATE INDEX idx_matches_footystats ON matches(footystats_id) WHERE footystats_id IS NOT NULL;
CREATE INDEX idx_matches_flashscore ON matches(flashscore_id) WHERE flashscore_id IS NOT NULL;
CREATE INDEX idx_matches_status_kickoff ON matches(status, kickoff) WHERE status = 'scheduled';

-- MATCH STATS
CREATE INDEX idx_match_stats_match ON match_stats(match_id);
CREATE INDEX idx_match_stats_source ON match_stats(source);

-- ODDS HISTORY (hypertable)
CREATE UNIQUE INDEX idx_odds_dedup
    ON odds_history(match_id, bookmaker_id, market_type, COALESCE(line, 0), period, content_hash, time);
CREATE INDEX idx_odds_match_market
    ON odds_history(match_id, market_type, bookmaker_id, time DESC);
CREATE INDEX idx_odds_closing
    ON odds_history(match_id, bookmaker_id, market_type) WHERE is_closing = TRUE;
CREATE INDEX idx_odds_source_job
    ON odds_history(source, collect_job_id);

-- LINEUPS
CREATE INDEX idx_lineups_match ON lineups(match_id);

-- INGESTION LOG
CREATE INDEX idx_ingestion_status ON ingestion_log(status, started_at DESC);
CREATE INDEX idx_ingestion_source ON ingestion_log(source, job_type, started_at DESC);
CREATE INDEX idx_ingestion_job_id ON ingestion_log(job_id);
