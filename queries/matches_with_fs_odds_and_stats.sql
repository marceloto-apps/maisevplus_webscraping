-- ==============================================================================
-- Consulta: Partidas com Odds e Estatísticas do Flashscore
--
-- Esta consulta retorna todas as partidas da tabela 'matches' que possuem
-- tanto estatísticas registradas na tabela 'match_stats_fs' quanto
-- registros de odds de pré-jogo da fonte 'flashscore' na tabela 'odds_history'.
--
-- Além disso, a consulta traz detalhes de:
--   1. Informações básicas da partida (Data, Campeonato, Temporada, Times, Placar, Status)
--   2. Estatísticas avançadas do Flashscore (xG, xGOT e xA para Full Time)
--   3. Odds de Fechamento (Closing Odds) da Bet365 para o mercado 1X2, se disponíveis.
-- ==============================================================================

WITH closing_1x2_odds AS (
    -- Seleciona as odds de fechamento da Bet365 para o mercado 1x2 (tempo regulamentar)
    SELECT DISTINCT ON (match_id)
        match_id,
        odds_1 AS bet365_odd_1,
        odds_x AS bet365_odd_x,
        odds_2 AS bet365_odd_2
    FROM odds_history oh
    JOIN bookmakers b ON oh.bookmaker_id = b.bookmaker_id
    WHERE oh.source = 'flashscore'
      AND oh.market_type = '1x2'
      AND oh.period = 'ft'
      AND oh.is_closing = TRUE
      AND b.name = 'bet365'
    ORDER BY match_id, time DESC
)

SELECT
    m.match_id,
    m.kickoff AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo' AS kickoff_brasil,
    l.code AS league_code,
    l.name AS league_name,
    s.label AS season,
    th.name_canonical AS home_team,
    ta.name_canonical AS away_team,
    m.ft_home AS goals_home,
    m.ft_away AS goals_away,
    m.status,

    -- Estatísticas avançadas do Flashscore
    ms_fs.xg_home_ft AS xg_home,
    ms_fs.xg_away_ft AS xg_away,
    ms_fs.xgot_home_ft AS xgot_home,
    ms_fs.xgot_away_ft AS xgot_away,
    ms_fs.xa_home_ft AS xa_home,
    ms_fs.xa_away_ft AS xa_away,

    -- Odds de Fechamento da Bet365 (1x2)
    o.bet365_odd_1,
    o.bet365_odd_x,
    o.bet365_odd_2

FROM matches m
JOIN leagues l ON m.league_id = l.league_id
JOIN seasons s ON m.season_id = s.season_id
JOIN teams th ON m.home_team_id = th.team_id
JOIN teams ta ON m.away_team_id = ta.team_id
-- Garante que tem estatísticas do Flashscore na tabela correspondente
JOIN match_stats_fs ms_fs ON ms_fs.match_id = m.match_id
-- Traz as odds da Bet365, se disponíveis
LEFT JOIN closing_1x2_odds o ON o.match_id = m.match_id
-- Garante que tem odds do Flashscore na tabela odds_history
WHERE EXISTS (
    SELECT 1 
    FROM odds_history oh 
    WHERE oh.match_id = m.match_id 
      AND oh.source = 'flashscore'
)
ORDER BY m.kickoff DESC;
