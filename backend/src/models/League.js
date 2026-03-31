const { query } = require('../config/database');

const League = {
  async findAll(filters = {}) {
    let sql = 'SELECT * FROM leagues WHERE 1=1';
    const params = [];

    if (filters.country) {
      params.push(filters.country);
      sql += ` AND country = $${params.length}`;
    }
    
    if (filters.active !== undefined) {
      params.push(filters.active);
      sql += ` AND active = $${params.length}`;
    }

    sql += ' ORDER BY tier ASC, name ASC';
    const { rows } = await query(sql, params);
    return rows;
  },

  async findById(id) {
    const { rows } = await query('SELECT * FROM leagues WHERE id = $1', [id]);
    return rows[0] || null;
  },

  async findByFootystatsId(footystatsId) {
    const { rows } = await query('SELECT * FROM leagues WHERE footystats_id = $1', [footystatsId]);
    return rows[0] || null;
  },

  async create(data) {
    const { name, country, footystats_id, season, tier, active = true } = data;
    const { rows } = await query(
      `INSERT INTO leagues (name, country, footystats_id, season, tier, active)
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING *`,
      [name, country, footystats_id, season, tier, active]
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
    const sql = `UPDATE leagues SET ${fields.join(', ')}, updated_at = NOW() WHERE id = $${idx} RETURNING *`;
    
    const { rows } = await query(sql, params);
    return rows[0] || null;
  },

  async upsertByFootystatsId(data) {
    const { name, country, footystats_id, season, tier = 3, active = true } = data;
    const { rows } = await query(
      `INSERT INTO leagues (name, country, footystats_id, season, tier, active)
       VALUES ($1, $2, $3, $4, $5, $6)
       ON CONFLICT (footystats_id) DO UPDATE SET
         name = EXCLUDED.name,
         country = EXCLUDED.country,
         season = EXCLUDED.season,
         tier = EXCLUDED.tier,
         active = EXCLUDED.active,
         updated_at = NOW()
       RETURNING *`,
      [name, country, footystats_id, season, tier, active]
    );
    return rows[0];
  }
};

module.exports = League;
