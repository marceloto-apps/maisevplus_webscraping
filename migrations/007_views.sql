-- =============================================================
-- 007_views.sql
-- Views auxiliares
-- Depende de: 002_reference_tables.sql, 003_data_tables.sql, 004_control_tables.sql
-- =============================================================

-- ============================================================
-- 10.1 Jogos de Hoje
-- ============================================================
CREATE OR REPLACE VIEW v_today_matches AS
SELECT
    m.match_id,
    m.kickoff,
    m.status,
    m.league_id,
    l.code AS league_code,
    l.tier,
    th.name_canonical AS home_team,
    ta.name_canonical AS away_team,
    m.flashscore_id,
    m.footystats_id,
    m.api_football_id
FROM matches m
JOIN leagues l ON l.league_id = m.league_id
JOIN teams th ON th.team_id = m.home_team_id
JOIN teams ta ON ta.team_id = m.away_team_id
WHERE m.kickoff::date = CURRENT_DATE
  AND m.status IN ('scheduled', 'live')
ORDER BY l.tier, m.kickoff;

-- ============================================================
-- 10.2 Closing Odds (CLV)
-- ============================================================
CREATE OR REPLACE VIEW v_closing_odds AS
SELECT
    oh.match_id,
    m.kickoff,
    m.league_id,
    oh.bookmaker_id,
    b.name AS bookmaker_name,
    b.clv_priority,
    oh.market_type,
    oh.line,
    oh.period,
    oh.odds_1,
    oh.odds_x,
    oh.odds_2,
    oh.overround,
    oh.time AS closing_time
FROM odds_history oh
JOIN matches m ON m.match_id = oh.match_id
JOIN bookmakers b ON b.bookmaker_id = oh.bookmaker_id
WHERE oh.is_closing = TRUE
ORDER BY oh.match_id, b.clv_priority NULLS LAST;

-- ============================================================
-- 10.3 Match Full — xG por Fonte
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
    m.goals_home_minutes,
    m.goals_away_minutes,

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

-- ============================================================
-- 10.4 Saúde da Ingestão
-- ============================================================
CREATE OR REPLACE VIEW v_ingestion_health AS
SELECT
    source,
    job_type,
    COUNT(*) FILTER (WHERE status = 'success')  AS success_count,
    COUNT(*) FILTER (WHERE status = 'partial')  AS partial_count,
    COUNT(*) FILTER (WHERE status = 'failed')   AS failed_count,
    MAX(finished_at) AS last_success_at,
    MAX(finished_at) FILTER (WHERE status = 'failed') AS last_failure_at,
    ROUND(AVG(records_new) FILTER (WHERE status IN ('success', 'partial'))) AS avg_records_new
FROM ingestion_log
WHERE started_at > NOW() - INTERVAL '48 hours'
GROUP BY source, job_type
ORDER BY source, job_type;

-- ============================================================
-- 10.5 Uso de API Keys
-- ============================================================
CREATE OR REPLACE VIEW v_api_keys_usage AS
SELECT
    service,
    key_label,
    usage_today,
    limit_daily,
    CASE WHEN limit_daily IS NOT NULL
        THEN ROUND(100.0 * usage_today / limit_daily, 1)
        ELSE NULL
    END AS pct_daily_used,
    usage_month,
    limit_monthly,
    CASE WHEN limit_monthly IS NOT NULL
        THEN ROUND(100.0 * usage_month / limit_monthly, 1)
        ELSE NULL
    END AS pct_monthly_used,
    is_active,
    last_used_at
FROM api_keys
ORDER BY service, key_label;
