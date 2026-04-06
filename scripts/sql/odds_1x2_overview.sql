-- Closing Odds 1X2 — Bet365, Pinnacle, Betfair Exchange
-- Uma linha por partida | Fonte: football_data (closing lines)
-- Filtro: descomente AND l.code para filtrar por liga

SELECT
    l.code                                          AS liga,
    m.kickoff::date                                 AS data,
    th.name_canonical                               AS home,
    ta.name_canonical                               AS away,
    COALESCE(m.ft_home::text,'?') || 'x' || COALESCE(m.ft_away::text,'?') AS placar,
    b365.odds_1  AS b365_h,
    b365.odds_x  AS b365_d,
    b365.odds_2  AS b365_a,
    pin.odds_1   AS pin_h,
    pin.odds_x   AS pin_d,
    pin.odds_2   AS pin_a,
    bfe.odds_1   AS bfe_h,
    bfe.odds_x   AS bfe_d,
    bfe.odds_2   AS bfe_a
FROM matches m
JOIN leagues l  ON l.league_id = m.league_id
JOIN teams th   ON th.team_id  = m.home_team_id
JOIN teams ta   ON ta.team_id  = m.away_team_id
LEFT JOIN odds_history b365
       ON b365.match_id     = m.match_id
      AND b365.bookmaker_id = (SELECT bookmaker_id FROM bookmakers WHERE name = 'bet365')
      AND b365.market_type  = '1x2'
      AND b365.is_closing   = TRUE
LEFT JOIN odds_history pin
       ON pin.match_id     = m.match_id
      AND pin.bookmaker_id = (SELECT bookmaker_id FROM bookmakers WHERE name = 'pinnacle')
      AND pin.market_type  = '1x2'
      AND pin.is_closing   = TRUE
LEFT JOIN odds_history bfe
       ON bfe.match_id     = m.match_id
      AND bfe.bookmaker_id = (SELECT bookmaker_id FROM bookmakers WHERE name = 'betfair_ex')
      AND bfe.market_type  = '1x2'
      AND bfe.is_closing   = TRUE
WHERE m.status = 'finished'
  AND (b365.odds_1 IS NOT NULL OR pin.odds_1 IS NOT NULL)
  -- AND l.code = 'ENG_PL'
  -- AND l.code IN ('ENG_PL','ESP_PD','GER_BL','ITA_SA','FRA_L1')
ORDER BY l.code, m.kickoff DESC;
