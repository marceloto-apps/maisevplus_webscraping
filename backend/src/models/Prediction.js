const { query } = require('../config/database');
const AppError = require('../utils/AppError');

const Prediction = {
  async findAll(filters = {}) {
    let sql = `
      SELECT p.*, 
             m.kickoff as match_date, m.status as match_status, m.ft_home, m.ft_away,
             th.name_canonical as home_team, ta.name_canonical as away_team 
      FROM predictions p
      JOIN matches m ON p.match_id = m.match_id
      JOIN teams th ON m.home_team_id = th.team_id
      JOIN teams ta ON m.away_team_id = ta.team_id
      WHERE 1=1
    `;
    const params = [];
    let paramIdx = 1;

    if (filters.status === 'pending') {
      sql += ` AND m.status = 'scheduled'`;
    }
    if (filters.model_version) {
      sql += ` AND p.model_version = $${paramIdx++}`;
      params.push(filters.model_version);
    }
    if (filters.suggested_bet) {
      sql += ` AND p.suggested_bet = $${paramIdx++}`;
      params.push(filters.suggested_bet);
    }
    if (filters.min_ev !== undefined) {
      sql += ` AND p.ev_percent >= $${paramIdx++}`;
      params.push(parseFloat(filters.min_ev));
    }
    if (filters.date_from) {
      sql += ` AND m.kickoff >= $${paramIdx++}`;
      params.push(filters.date_from);
    }
    if (filters.date_to) {
      sql += ` AND m.kickoff <= $${paramIdx++}`;
      params.push(filters.date_to);
    }

    sql += ` ORDER BY m.kickoff DESC, p.ev_percent DESC`;

    const limit = parseInt(filters.limit, 10) || 50;
    const offset = parseInt(filters.offset, 10) || 0;
    
    sql += ` LIMIT $${paramIdx++} OFFSET $${paramIdx++}`;
    params.push(limit, offset);

    const { rows } = await query(sql, params);
    return rows;
  },

  async findById(id) {
    const { rows } = await query('SELECT * FROM predictions WHERE id = $1', [id]);
    if (!rows.length) return null;
    return rows[0];
  },

  async findByMatchId(matchId) {
    const { rows } = await query('SELECT * FROM predictions WHERE match_id = $1 ORDER BY ev_pct DESC', [matchId]);
    return rows;
  },

  async create(data) {
    // Wrapper pra manter compatibilidade retroativa p/ chamadas n-transacionais
    return this.createWithClient({ query }, data);
  },

  async createWithClient(client, data) {
    const {
      match_id, model_name, model_version, market, selection,
      predicted_prob, best_odd_available, bookmaker, confidence
    } = data;

    // Cálculo dinâmico analítico na inserção
    const fair_odd = 1 / predicted_prob;
    const implied_prob = 1 / best_odd_available;
    const edge = predicted_prob - implied_prob;
    // EV = (Odd * Prob) - 1
    const ev_pct = ((best_odd_available * predicted_prob) - 1) * 100;
    
    // Fração de Kelly para controle seguro da banca baseando-se nas predições do banco: f = (bp - q)/b
    const b = best_odd_available - 1;
    const q = 1 - predicted_prob;
    const kelly_fraction = b > 0 ? Math.max(0, (b * predicted_prob - q) / b) : 0;
    const { rows } = await client.query(
      `INSERT INTO predictions (
         match_id, model_name, model_version, market, selection, 
         predicted_prob, fair_odd, best_odd_available, bookmaker, 
         ev_pct, edge, kelly_fraction, confidence, status
       ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, 'pending')
       ON CONFLICT (match_id, model_name, market, selection) DO UPDATE SET
         predicted_prob = EXCLUDED.predicted_prob,
         fair_odd = EXCLUDED.fair_odd,
         best_odd_available = EXCLUDED.best_odd_available,
         bookmaker = EXCLUDED.bookmaker,
         ev_pct = EXCLUDED.ev_pct,
         edge = EXCLUDED.edge,
         kelly_fraction = EXCLUDED.kelly_fraction,
         confidence = EXCLUDED.confidence,
         updated_at = NOW()
       RETURNING *`,
      [
        match_id, model_name, model_version, market, selection,
        predicted_prob, fair_odd, best_odd_available, bookmaker,
        ev_pct, edge, kelly_fraction, confidence
      ]
    );

    return rows[0];
  },

  async updateStatus(id, status, result) {
    const { rows } = await query(
      `UPDATE predictions SET status = $1, result = $2, updated_at = NOW() WHERE id = $3 RETURNING *`,
      [status, result, id]
    );
    return rows[0] || null;
  },

  async getPerformanceStats(filters = {}) {
    let whereClauses = 'WHERE p.status IN (\'won\', \'lost\')';
    const params = [];
    let idx = 1;

    if (filters.model_name) {
      whereClauses += ` AND p.model_name = $${idx++}`;
      params.push(filters.model_name);
    }
    
    // Retorna sumarização consolidada
    const sql = `
      SELECT 
        p.model_name,
        p.market,
        COUNT(*) as total_predictions,
        SUM(CASE WHEN p.status = 'won' THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN p.status = 'lost' THEN 1 ELSE 0 END) as losses,
        -- ROI Virtual baseando em Flat Stake de 1 uni
        SUM(CASE WHEN p.status = 'won' THEN (p.best_odd_available - 1) ELSE -1 END) / COUNT(*) * 100 as roi_pct,
        -- Hit rate real
        AVG(CASE WHEN p.status = 'won' THEN 1.0 ELSE 0.0 END) * 100 as hit_rate_pct,
        -- Avg previsto
        AVG(p.predicted_prob) * 100 as avg_predicted_prob
      FROM predictions p
      ${whereClauses}
      GROUP BY p.model_name, p.market
      ORDER BY roi_pct DESC
    `;
    const { rows } = await query(sql, params);
    return rows;
  },

  async getPendingForSettlement() {
    // Retorna predições 'pending' cujo match já encerrou (finished)
    const sql = `
      SELECT p.*, m.home_score, m.away_score, m.ht_home_score, m.ht_away_score 
      FROM predictions p
      JOIN matches m ON p.match_id = m.id
      WHERE p.status = 'pending' AND m.status = 'finished'
    `;
    const { rows } = await query(sql);
    return rows;
  }
};

module.exports = Prediction;
