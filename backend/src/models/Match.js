const { query } = require('../config/database');
const AppError = require('../utils/AppError');

const Match = {
  async findAll(filters = {}) {
    let sql = `
      SELECT m.*, 
             l.name AS league_name, l.country AS league_country,
             th.name AS home_team_name, th.logo_url AS home_logo_url,
             ta.name AS away_team_name, ta.logo_url AS away_logo_url
      FROM matches m
      JOIN leagues l ON m.league_id = l.id
      JOIN teams th ON m.home_team_id = th.id
      JOIN teams ta ON m.away_team_id = ta.id
      WHERE 1=1
    `;
    const params = [];
    let paramIdx = 1;

    if (filters.league_id) {
      sql += ` AND m.league_id = $${paramIdx++}`;
      params.push(filters.league_id);
    }
    if (filters.status) {
      sql += ` AND m.status = $${paramIdx++}`;
      params.push(filters.status);
    }
    if (filters.date_from) {
      sql += ` AND m.match_date >= $${paramIdx++}`;
      params.push(filters.date_from);
    }
    if (filters.date_to) {
      sql += ` AND m.match_date <= $${paramIdx++}`;
      params.push(filters.date_to);
    }
    if (filters.team_id) {
      sql += ` AND (m.home_team_id = $${paramIdx} OR m.away_team_id = $${paramIdx})`;
      params.push(filters.team_id);
      paramIdx++;
    }

    sql += ` ORDER BY m.match_date DESC`;

    const limit = parseInt(filters.limit, 10) || 50;
    const offset = parseInt(filters.offset, 10) || 0;
    
    sql += ` LIMIT $${paramIdx++} OFFSET $${paramIdx++}`;
    params.push(limit, offset);

    const { rows } = await query(sql, params);
    return rows;
  },

  async findById(id) {
    const sql = `
      SELECT m.*, 
             l.name AS league_name, l.country AS league_country,
             th.name AS home_team_name, th.logo_url AS home_logo_url,
             ta.name AS away_team_name, ta.logo_url AS away_logo_url,
             (SELECT row_to_json(ms) FROM match_stats ms WHERE ms.match_id = m.id AND ms.team_id = m.home_team_id LIMIT 1) as home_stats,
             (SELECT row_to_json(ms) FROM match_stats ms WHERE ms.match_id = m.id AND ms.team_id = m.away_team_id LIMIT 1) as away_stats
      FROM matches m
      JOIN leagues l ON m.league_id = l.id
      JOIN teams th ON m.home_team_id = th.id
      JOIN teams ta ON m.away_team_id = ta.id
      WHERE m.id = $1
    `;
    const { rows } = await query(sql, [id]);
    return rows[0] || null;
  },

  async findByFootystatsId(footystatsId) {
    const { rows } = await query('SELECT * FROM matches WHERE footystats_id = $1', [footystatsId]);
    return rows[0] || null;
  },

  async findUpcoming(days = 7) {
    const sql = `
      SELECT m.*, l.name AS league_name, th.name AS home_team_name, ta.name AS away_team_name
      FROM matches m
      JOIN leagues l ON m.league_id = l.id
      JOIN teams th ON m.home_team_id = th.id
      JOIN teams ta ON m.away_team_id = ta.id
      WHERE m.status = 'scheduled' 
        AND m.match_date BETWEEN NOW() AND NOW() + INTERVAL '1 day' * $1
      ORDER BY m.match_date ASC
    `;
    const { rows } = await query(sql, [days]);
    return rows;
  },

  async create(data) {
    const { 
      league_id, home_team_id, away_team_id, match_date, status = 'scheduled',
      home_score, away_score, ht_home_score, ht_away_score, 
      footystats_id, season, round 
    } = data;
    
    const { rows } = await query(
      `INSERT INTO matches (
        league_id, home_team_id, away_team_id, match_date, status, 
        home_score, away_score, ht_home_score, ht_away_score, 
        footystats_id, season, round
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
      RETURNING *`,
      [league_id, home_team_id, away_team_id, match_date, status, home_score, away_score, ht_home_score, ht_away_score, footystats_id, season, round]
    );
    return rows[0];
  },

  async update(id, data) {
    const fields = [];
    const params = [];
    let idx = 1;
    
    for (const [key, value] of Object.entries(data)) {
      if (value !== undefined) {
        fields.push(`${key} = $${idx}`);
        params.push(value);
        idx++;
      }
    }
    
    if (fields.length === 0) return this.findById(id);

    params.push(id);
    const sql = `UPDATE matches SET ${fields.join(', ')}, updated_at = NOW() WHERE id = $${idx} RETURNING *`;
    const { rows } = await query(sql, params);
    return rows[0] || null;
  },

  async upsertByFootystatsId(data) {
    const { 
      league_id, home_team_id, away_team_id, match_date, status = 'scheduled',
      home_score = null, away_score = null, ht_home_score = null, ht_away_score = null, 
      footystats_id, season, round 
    } = data;

    const { rows } = await query(
      `INSERT INTO matches (
        league_id, home_team_id, away_team_id, match_date, status, 
        home_score, away_score, ht_home_score, ht_away_score, 
        footystats_id, season, round
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
      ON CONFLICT (footystats_id) DO UPDATE SET
        match_date = EXCLUDED.match_date,
        status = EXCLUDED.status,
        home_score = EXCLUDED.home_score,
        away_score = EXCLUDED.away_score,
        ht_home_score = EXCLUDED.ht_home_score,
        ht_away_score = EXCLUDED.ht_away_score,
        updated_at = NOW()
      RETURNING *`,
      [league_id, home_team_id, away_team_id, match_date, status, home_score, away_score, ht_home_score, ht_away_score, footystats_id, season, round]
    );
    return rows[0];
  },

  async updateResult(id, homeScore, awayScore, htHome = null, htAway = null) {
    const { rows } = await query(
      `UPDATE matches SET
         home_score = $1, away_score = $2,
         ht_home_score = $3, ht_away_score = $4,
         status = 'finished',
         updated_at = NOW()
       WHERE id = $5
       RETURNING *`,
      [homeScore, awayScore, htHome, htAway, id]
    );
    
    if (!rows.length) {
      throw new AppError('Partida não encontrada para atualizar resultado', 404, 'NOT_FOUND');
    }
    return rows[0];
  }
};

module.exports = Match;
