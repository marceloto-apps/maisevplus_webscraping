DROP TABLE IF EXISTS scraping_health;
CREATE TABLE scraping_health (
    id SERIAL PRIMARY KEY,
    run_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source VARCHAR(50) NOT NULL,
    total_matches INT NOT NULL,
    matches_with_odds INT NOT NULL,
    bet365_found INT NOT NULL DEFAULT 0,
    pinnacle_found INT NOT NULL DEFAULT 0,
    avg_bookmakers NUMERIC(5, 2) NOT NULL DEFAULT 0,
    unidentified_rows INT NOT NULL DEFAULT 0,
    unknown_bookmakers TEXT[] NOT NULL DEFAULT '{}',
    parse_errors INT NOT NULL DEFAULT 0,
    success_rate NUMERIC(5, 2) NOT NULL,
    alert_level TEXT NOT NULL,
    job_id VARCHAR(100)
);

CREATE INDEX idx_scraping_health_time ON scraping_health (run_ts DESC);
