-- =============================================================
-- coverage_report.sql
-- Relatório de cobertura de dados por liga e temporada.
--
-- Identifica, para cada partida, quais fontes têm dados:
--   - match_stats footystats  : sentinel pre_match_home_ppg IS NOT NULL
--                               (coluna exclusiva da migration 010_footystats_expansion)
--   - match_stats api_football: sentinel total_passes_home IS NOT NULL
--                               OR expected_goals_home IS NOT NULL
--                               (colunas exclusivas da migration 016_api_football_stats)
--   - match_stats flashscore  : sentinel xg_fs_home IS NOT NULL OR xgot_fs_home IS NOT NULL
--                               (colunas _fs_ exclusivas da migration 012_flashscore_stats)
--   - odds football-data      : odds_history.source = 'football_data'
--   - odds flashscore         : odds_history.source = 'flashscore'
-- =============================================================

WITH

-- ── 1. Base: todas as partidas finalizadas ─────────────────────────────────
base AS (
    SELECT
        m.match_id,
        l.code          AS league_code,
        l.name          AS league_name,
        s.label         AS season,
        m.kickoff::date AS match_date,
        m.status,
        m.footystats_id,
        m.api_football_id,
        m.flashscore_id,
        m.football_data_id
    FROM matches m
    JOIN leagues l ON l.league_id = m.league_id
    JOIN seasons s ON s.season_id = m.season_id
    WHERE m.status = 'finished'
),

-- ── 2. Presença de stats por fonte ─────────────────────────────────────────
stats_flags AS (
    SELECT
        ms.match_id,

        -- FootyStats: pre_match_home_ppg é exclusiva da migration 010_footystats_expansion.
        -- Nenhuma outra fonte preenche essa coluna.
        MAX(CASE WHEN ms.pre_match_home_ppg IS NOT NULL
             THEN 1 ELSE 0 END)                              AS has_footystats_stats,

        -- API-Football: total_passes_home e expected_goals_home são exclusivas
        -- da migration 016_api_football_stats. Nenhuma outra fonte preenche.
        MAX(CASE WHEN ms.total_passes_home IS NOT NULL
                   OR ms.expected_goals_home IS NOT NULL
             THEN 1 ELSE 0 END)                              AS has_apifootball_stats,

        -- Flashscore: colunas _fs_ são exclusivas da migration 012_flashscore_stats.
        -- O collector insere nessas colunas independente do valor de source.
        MAX(CASE WHEN ms.xg_fs_home IS NOT NULL
                   OR ms.xgot_fs_home IS NOT NULL
                   OR ms.xa_fs_home   IS NOT NULL
                   OR ms.crosses_fs_home IS NOT NULL
             THEN 1 ELSE 0 END)                              AS has_flashscore_stats

    FROM match_stats ms
    GROUP BY ms.match_id
),

-- ── 3. Presença de odds por fonte ──────────────────────────────────────────
odds_flags AS (
    SELECT
        match_id,
        MAX(CASE WHEN source = 'football_data' THEN 1 ELSE 0 END) AS has_fd_odds,
        MAX(CASE WHEN source = 'flashscore'    THEN 1 ELSE 0 END) AS has_fs_odds
    FROM odds_history
    GROUP BY match_id
)

-- ── 4. Resultado final agrupado ────────────────────────────────────────────
SELECT
    b.league_code,
    b.league_name,
    b.season,

    COUNT(*)                                                  AS total_matches,

    -- ── Stats ──────────────────────────────────────────────────────────────
    COUNT(*) FILTER (WHERE COALESCE(sf.has_footystats_stats, 0) = 1)
                                                              AS footystats_stats,
    ROUND(
        COUNT(*) FILTER (WHERE COALESCE(sf.has_footystats_stats, 0) = 1)
        * 100.0 / NULLIF(COUNT(*), 0), 1
    )                                                         AS footystats_pct,

    COUNT(*) FILTER (WHERE COALESCE(sf.has_apifootball_stats, 0) = 1)
                                                              AS apifootball_stats,
    ROUND(
        COUNT(*) FILTER (WHERE COALESCE(sf.has_apifootball_stats, 0) = 1)
        * 100.0 / NULLIF(COUNT(*), 0), 1
    )                                                         AS apifootball_pct,

    COUNT(*) FILTER (WHERE COALESCE(sf.has_flashscore_stats, 0) = 1)
                                                              AS flashscore_stats,
    ROUND(
        COUNT(*) FILTER (WHERE COALESCE(sf.has_flashscore_stats, 0) = 1)
        * 100.0 / NULLIF(COUNT(*), 0), 1
    )                                                         AS flashscore_pct,

    -- ── Odds ───────────────────────────────────────────────────────────────
    COUNT(*) FILTER (WHERE COALESCE(of_.has_fd_odds, 0) = 1)
                                                              AS football_data_odds,
    ROUND(
        COUNT(*) FILTER (WHERE COALESCE(of_.has_fd_odds, 0) = 1)
        * 100.0 / NULLIF(COUNT(*), 0), 1
    )                                                         AS football_data_odds_pct,

    COUNT(*) FILTER (WHERE COALESCE(of_.has_fs_odds, 0) = 1)
                                                              AS flashscore_odds,
    ROUND(
        COUNT(*) FILTER (WHERE COALESCE(of_.has_fs_odds, 0) = 1)
        * 100.0 / NULLIF(COUNT(*), 0), 1
    )                                                         AS flashscore_odds_pct,

    -- ── Cobertura combinada (tem tudo) ─────────────────────────────────────
    COUNT(*) FILTER (
        WHERE COALESCE(sf.has_footystats_stats,  0) = 1
          AND COALESCE(sf.has_apifootball_stats, 0) = 1
          AND COALESCE(sf.has_flashscore_stats,  0) = 1
          AND COALESCE(of_.has_fd_odds,           0) = 1
          AND COALESCE(of_.has_fs_odds,           0) = 1
    )                                                         AS fully_covered,
    ROUND(
        COUNT(*) FILTER (
            WHERE COALESCE(sf.has_footystats_stats,  0) = 1
              AND COALESCE(sf.has_apifootball_stats, 0) = 1
              AND COALESCE(sf.has_flashscore_stats,  0) = 1
              AND COALESCE(of_.has_fd_odds,           0) = 1
              AND COALESCE(of_.has_fs_odds,           0) = 1
        ) * 100.0 / NULLIF(COUNT(*), 0), 1
    )                                                         AS fully_covered_pct

FROM base b
LEFT JOIN stats_flags sf ON sf.match_id = b.match_id
LEFT JOIN odds_flags  of_ ON of_.match_id = b.match_id

GROUP BY
    b.league_code,
    b.league_name,
    b.season

ORDER BY
    b.league_code,
    b.season DESC;


-- =============================================================
-- VARIAÇÃO: detalhamento por partida (linha por jogo)
-- Útil para exportar para CSV e filtrar buracos específicos.
-- Descomente o bloco abaixo para usar no lugar do agrupado:
-- =============================================================
/*
SELECT
    b.league_code,
    b.season,
    b.match_date,
    b.match_id,
    b.status,
    b.footystats_id     IS NOT NULL                           AS id_footystats,
    b.api_football_id   IS NOT NULL                           AS id_apifootball,
    b.flashscore_id     IS NOT NULL                           AS id_flashscore,
    b.football_data_id  IS NOT NULL                           AS id_football_data,

    COALESCE(sf.has_footystats_stats,  0) = 1                AS stats_footystats,
    COALESCE(sf.has_apifootball_stats, 0) = 1                AS stats_apifootball,
    COALESCE(sf.has_flashscore_stats,  0) = 1                AS stats_flashscore,
    COALESCE(of_.has_fd_odds,          0) = 1                AS odds_football_data,
    COALESCE(of_.has_fs_odds,          0) = 1                AS odds_flashscore

FROM base b
LEFT JOIN stats_flags sf  ON sf.match_id  = b.match_id
LEFT JOIN odds_flags  of_ ON of_.match_id = b.match_id

ORDER BY b.league_code, b.season DESC, b.match_date;
*/
