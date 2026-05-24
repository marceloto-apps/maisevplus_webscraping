-- 1. Contagem de rows migradas
SELECT 
    (SELECT COUNT(*) FROM match_stats_fs) AS fs_rows_migradas,
    (SELECT COUNT(*) FROM match_stats_fs WHERE xg_home_ft IS NOT NULL OR xg_away_ft IS NOT NULL) AS fs_rows_com_xg;

-- 2. Conferir integridade referencial (deve retornar 0)
SELECT COUNT(*) AS orfaos
FROM match_stats_fs ms_fs
LEFT JOIN matches m ON ms_fs.match_id = m.match_id
WHERE m.match_id IS NULL;

-- 3. Validar criação das flags
SELECT 
    COUNT(*) FILTER (WHERE flashscore_stats_collected = FALSE) AS stats_pendentes,
    COUNT(*) FILTER (WHERE flashscore_odds_collected  = FALSE) AS odds_pendentes,
    COUNT(*) AS total_matches
FROM matches;

-- 4. Validar primary_source nas leagues
SELECT primary_source, COUNT(*) FROM leagues GROUP BY primary_source;

-- 5. Validar view recriada (executa sem erro = OK)
SELECT COUNT(*) FROM v_match_full LIMIT 1;
