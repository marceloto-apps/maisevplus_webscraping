const { query, getClient } = require('../config/database');

const Odds = {
  async findByMatchId(matchId, filters = {}) {
    let sql = 'SELECT * FROM odds WHERE match_id = $1';
    const params = [matchId];
    let paramIdx = 2;

    if (filters.market) {
      sql += ` AND market = $${paramIdx++}`;
      params.push(filters.market);
    }
    if (filters.bookmaker) {
      sql += ` AND bookmaker = $${paramIdx++}`;
      params.push(filters.bookmaker);
    }
    
    sql += ' ORDER BY captured_at DESC';
    const { rows } = await query(sql, params);
    return rows;
  },

  async getLatestByMatch(matchId) {
    // Retorna a última odd capturada de cada combinação(market, selection, bookmaker)
    const sql = `
      SELECT DISTINCT ON (market, selection, bookmaker) *
      FROM odds 
      WHERE match_id = $1
      ORDER BY market, selection, bookmaker, captured_at DESC
    `;
    const { rows } = await query(sql, [matchId]);
    return rows;
  },

  async getOpeningByMatch(matchId) {
    const sql = `
      SELECT * FROM odds 
      WHERE match_id = $1 AND is_opening = TRUE
    `;
    const { rows } = await query(sql, [matchId]);
    return rows;
  },

  async getClosingByMatch(matchId) {
    const sql = `
      SELECT * FROM odds 
      WHERE match_id = $1 AND is_closing = TRUE
    `;
    const { rows } = await query(sql, [matchId]);
    return rows;
  },

  async getOddsMovement(matchId, market, selection) {
    const sql = `
      SELECT bookmaker, odd_value, implied_prob, captured_at
      FROM odds
      WHERE match_id = $1 AND market = $2 AND selection = $3
      ORDER BY captured_at ASC
    `;
    const { rows } = await query(sql, [matchId, market, selection]);
    return rows;
  },

  async insertBatch(oddsArray) {
    if (!oddsArray || !oddsArray.length) return 0;
    
    // Concatenação de batch eficiente para PostgreSQL com valores em array unidimensional
    const client = await getClient();
    try {
      const values = [];
      const queryParams = [];
      let counter = 1;

      for (const odd of oddsArray) {
        const impliedProb = odd.implied_prob || (1 / odd.odd_value);
        values.push(`($${counter++}, $${counter++}, $${counter++}, $${counter++}, $${counter++}, $${counter++}, $${counter++}, $${counter++}, COALESCE($${counter++}, NOW()))`);
        queryParams.push(
          odd.match_id, odd.bookmaker, odd.market, odd.selection, 
          odd.odd_value, impliedProb, 
          odd.is_opening || false, odd.is_closing || false,
          odd.captured_at || null
        );
      }

      const sql = `
        INSERT INTO odds (match_id, bookmaker, market, selection, odd_value, implied_prob, is_opening, is_closing, captured_at)
        VALUES ${values.join(', ')}
        RETURNING id
      `;

      const { rows } = await client.query(sql, queryParams);
      return rows.length;
    } finally {
        client.release();
    }
  }
};

module.exports = Odds;
