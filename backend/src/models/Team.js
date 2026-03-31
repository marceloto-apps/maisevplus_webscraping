const { query } = require('../config/database');

const Team = {
  async findAll(filters = {}) {
    let sql = 'SELECT t.* FROM teams t ';
    const params = [];
    let idx = 1;

    // Se quisermos filtrar por league_id, fazemos um JOIN em match ou usamos team_stats_agg (idealmente temos league_id)
    // Usando subquery simples via season atual (em team_stats_agg)
    if (filters.league_id) {
      sql += 'JOIN team_stats_agg tsa ON tsa.team_id = t.id ';
      params.push(filters.league_id);
      sql += `WHERE tsa.league_id = $${idx} `;
      idx++;
    } else {
      sql += 'WHERE 1=1 ';
    }

    if (filters.country) {
      params.push(filters.country);
      sql += `AND t.country = $${idx} `;
      idx++;
    }
    
    if (filters.active !== undefined) {
      params.push(filters.active);
      sql += `AND t.active = $${idx} `;
      idx++;
    }

    sql += 'ORDER BY t.name ASC';
    const { rows } = await query(sql, params);
    return rows;
  },

  async findById(id) {
    const { rows } = await query('SELECT * FROM teams WHERE id = $1', [id]);
    return rows[0] || null;
  },

  async findByFootystatsId(footystatsId) {
    const { rows } = await query('SELECT * FROM teams WHERE footystats_id = $1', [footystatsId]);
    return rows[0] || null;
  },

  async create(data) {
    const { name, country, footystats_id, logo_url, active = true } = data;
    const { rows } = await query(
      `INSERT INTO teams (name, country, footystats_id, logo_url, active)
       VALUES ($1, $2, $3, $4, $5)
       RETURNING *`,
      [name, country, footystats_id, logo_url, active]
    );
    return rows[0];
  },

  async update(id, data) {
    const fields = [];
    const params = [];
    let idx = 1;
    
    for (const [key, value] of Object.entries(data)) {
      fields.push(`${key} = $${idx}`);
      params.push(value);
      idx++;
    }
    
    if (fields.length === 0) return this.findById(id);

    params.push(id);
    const sql = `UPDATE teams SET ${fields.join(', ')}, updated_at = NOW() WHERE id = $${idx} RETURNING *`;
    
    const { rows } = await query(sql, params);
    return rows[0] || null;
  },

  async upsertByFootystatsId(data) {
    const { name, country, footystats_id, logo_url, active = true } = data;
    const { rows } = await query(
      `INSERT INTO teams (name, country, footystats_id, logo_url, active)
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (footystats_id) DO UPDATE SET
         name = EXCLUDED.name,
         country = EXCLUDED.country,
         logo_url = EXCLUDED.logo_url,
         active = EXCLUDED.active,
         updated_at = NOW()
       RETURNING *`,
      [name, country, footystats_id, logo_url, active]
    );
    return rows[0];
  }
};

module.exports = Team;
