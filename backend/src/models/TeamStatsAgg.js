const { query } = require('../config/database');

const TeamStatsAgg = {
  async findByTeam(teamId, season) {
    const { rows } = await query(
      'SELECT * FROM team_stats_agg WHERE team_id = $1 AND season = $2 LIMIT 1',
      [teamId, season]
    );
    return rows[0] || null;
  },

  async findByLeague(leagueId, season) {
    const { rows } = await query(
      `SELECT tsa.*, t.name as team_name, t.logo_url
       FROM team_stats_agg tsa
       JOIN teams t ON tsa.team_id = t.id
       WHERE tsa.league_id = $1 AND tsa.season = $2
       ORDER BY tsa.wins DESC, tsa.draws DESC`,
      [leagueId, season]
    );
    return rows;
  },

  async upsert(data) {
    const {
      team_id, league_id, season, matches_played, wins, draws, losses,
      goals_for, goals_against, xg_for, xg_against, avg_possession, avg_corners,
      avg_shots, avg_cards, btts_pct, over25_pct, clean_sheet_pct, scoring_first_pct,
      elo_rating, form_last5
    } = data;

    const { rows } = await query(
      `INSERT INTO team_stats_agg (
        team_id, league_id, season, matches_played, wins, draws, losses,
        goals_for, goals_against, xg_for, xg_against, avg_possession, avg_corners,
        avg_shots, avg_cards, btts_pct, over25_pct, clean_sheet_pct, scoring_first_pct,
        elo_rating, form_last5
      ) VALUES (
        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
      )
      ON CONFLICT (team_id, league_id, season) DO UPDATE SET
        matches_played = EXCLUDED.matches_played,
        wins = EXCLUDED.wins,
        draws = EXCLUDED.draws,
        losses = EXCLUDED.losses,
        goals_for = EXCLUDED.goals_for,
        goals_against = EXCLUDED.goals_against,
        xg_for = EXCLUDED.xg_for,
        xg_against = EXCLUDED.xg_against,
        avg_possession = EXCLUDED.avg_possession,
        avg_corners = EXCLUDED.avg_corners,
        avg_shots = EXCLUDED.avg_shots,
        avg_cards = EXCLUDED.avg_cards,
        btts_pct = EXCLUDED.btts_pct,
        over25_pct = EXCLUDED.over25_pct,
        clean_sheet_pct = EXCLUDED.clean_sheet_pct,
        scoring_first_pct = EXCLUDED.scoring_first_pct,
        elo_rating = EXCLUDED.elo_rating,
        form_last5 = EXCLUDED.form_last5
      RETURNING *`,
      [
        team_id, league_id, season, matches_played, wins, draws, losses,
        goals_for, goals_against, xg_for, xg_against, avg_possession, avg_corners,
        avg_shots, avg_cards, btts_pct, over25_pct, clean_sheet_pct, scoring_first_pct,
        elo_rating, form_last5
      ]
    );
    return rows[0];
  },

  // Recalculo puro em SQL baseando-se nas partidas da temporada
  async recalculate(teamId, leagueId, season) {
    const rawSql = `
      WITH team_matches AS (
        SELECT 
          m.id, 
          m.home_score, m.away_score,
          (m.home_team_id = $1) as is_home,
          (m.home_score > 0 AND m.away_score > 0) as is_btts,
          ((m.home_score + m.away_score) > 2.5) as is_over25,
          CASE WHEN (m.home_team_id = $1 AND m.away_score = 0) OR (m.away_team_id = $1 AND m.home_score = 0) THEN true ELSE false END as is_clean_sheet
        FROM matches m
        WHERE m.league_id = $2 
          AND m.season = $3 
          AND m.status = 'finished' 
          AND (m.home_team_id = $1 OR m.away_team_id = $1)
      ),
      agg_data AS (
        SELECT 
          COUNT(*) as m_played,
          SUM(CASE WHEN is_home AND home_score > away_score THEN 1 
                   WHEN NOT is_home AND away_score > home_score THEN 1 ELSE 0 END) as w,
          SUM(CASE WHEN home_score = away_score THEN 1 ELSE 0 END) as d,
          SUM(CASE WHEN is_home AND home_score < away_score THEN 1 
                   WHEN NOT is_home AND away_score < home_score THEN 1 ELSE 0 END) as l,
          SUM(CASE WHEN is_home THEN home_score ELSE away_score END) as gf,
          SUM(CASE WHEN is_home THEN away_score ELSE home_score END) as ga,
          AVG(CASE WHEN is_btts THEN 1.0 ELSE 0.0 END) * 100 as pct_btts,
          AVG(CASE WHEN is_over25 THEN 1.0 ELSE 0.0 END) * 100 as pct_over25,
          AVG(CASE WHEN is_clean_sheet THEN 1.0 ELSE 0.0 END) * 100 as pct_cs
        FROM team_matches
      ),
      stats_avg AS (
        SELECT 
          AVG(possession) as avg_poss,
          AVG(shots_total) as avg_sh,
          AVG(corners) as avg_cn,
          AVG(yellow_cards + red_cards) as avg_card,
          SUM(xg) as total_xg
        FROM match_stats ms
        JOIN team_matches tm ON ms.match_id = tm.id AND ms.team_id = $1
      )
      
      -- Realiza o Upsert combinando CTEs
      -- TODO (Fase 4): complementar xg_against, scoring_first_pct e form_last5 via statsService
      INSERT INTO team_stats_agg (
        team_id, league_id, season, matches_played, wins, draws, losses,
        goals_for, goals_against, btts_pct, over25_pct, clean_sheet_pct,
        avg_possession, avg_shots, avg_corners, avg_cards, xg_for
      )
      SELECT 
        $1, $2, $3, 
        a.m_played, a.w, a.d, a.l, a.gf, a.ga, 
        COALESCE(a.pct_btts, 0), COALESCE(a.pct_over25, 0), COALESCE(a.pct_cs, 0),
        COALESCE(s.avg_poss, 0), COALESCE(s.avg_sh, 0), COALESCE(s.avg_cn, 0), COALESCE(s.avg_card, 0), COALESCE(s.total_xg, 0)
      FROM agg_data a CROSS JOIN stats_avg s
      ON CONFLICT (team_id, league_id, season) DO UPDATE SET
        matches_played = EXCLUDED.matches_played,
        wins = EXCLUDED.wins, draws = EXCLUDED.draws, losses = EXCLUDED.losses,
        goals_for = EXCLUDED.goals_for, goals_against = EXCLUDED.goals_against,
        btts_pct = EXCLUDED.btts_pct, over25_pct = EXCLUDED.over25_pct, clean_sheet_pct = EXCLUDED.clean_sheet_pct,
        avg_possession = EXCLUDED.avg_possession, avg_shots = EXCLUDED.avg_shots, 
        avg_corners = EXCLUDED.avg_corners, avg_cards = EXCLUDED.avg_cards,
        xg_for = EXCLUDED.xg_for
      RETURNING *;
    `;
    const { rows } = await query(rawSql, [teamId, leagueId, season]);
    return rows[0];
  }
};

module.exports = TeamStatsAgg;
