const { query, getClient } = require('../config/database');
const AppError = require('../utils/AppError');
const Bankroll = require('./Bankroll');

const Bet = {
  async findAll(filters = {}) {
    let sql = `
      SELECT b.*, 
             m.match_date, th.name as home_name, ta.name as away_name,
             p.model_name, p.ev_pct
      FROM bets b
      JOIN matches m ON b.match_id = m.id
      JOIN teams th ON m.home_team_id = th.id
      JOIN teams ta ON m.away_team_id = ta.id
      LEFT JOIN predictions p ON b.prediction_id = p.id
      WHERE 1=1
    `;
    const params = [];
    let paramIdx = 1;

    if (filters.status) {
      sql += ` AND b.status = $${paramIdx++}`;
      params.push(filters.status);
    }
    
    sql += ` ORDER BY b.placed_at DESC`;

    const limit = parseInt(filters.limit, 10) || 50;
    const offset = parseInt(filters.offset, 10) || 0;
    
    sql += ` LIMIT $${paramIdx++} OFFSET $${paramIdx++}`;
    params.push(limit, offset);

    const { rows } = await query(sql, params);
    return rows;
  },

  async findById(id) {
    const { rows } = await query('SELECT * FROM bets WHERE id = $1', [id]);
    return rows[0] || null;
  },

  /**
   * Registra a aposta NO BANCO (transação que tira da banca).
   */
  async create(data) {
    const {
      prediction_id, match_id, market, selection, odd_placed, stake, bookmaker
    } = data;

    const potential_return = stake * odd_placed;
    
    // Obtemos database client (pool connect) para transacionar Bet + Bankroll juntos
    const client = await getClient();
    try {
      await client.query('BEGIN');
      await client.query('SELECT pg_advisory_xact_lock(1)');
      
      // Criando a aposta (status 'open')
      const betInsertSql = `
        INSERT INTO bets (
          prediction_id, match_id, market, selection, odd_placed, stake, 
          potential_return, bookmaker, status, placed_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'open', NOW())
        RETURNING *
      `;
      const resultBet = await client.query(betInsertSql, [
        prediction_id, match_id, market, selection, odd_placed, stake, potential_return, bookmaker
      ]);
      const newBet = resultBet.rows[0];

      // Deduzindo da bankroll
      // Passamos o `client` externo para utilizar do lock/transação já aberta.
      await Bankroll.addEntry({
        operation: 'bet',
        amount: stake,
        bet_id: newBet.id,
        description: `Staked in Bet #${newBet.id} on ${market} - ${selection}`
      }, client);

      await client.query('COMMIT');
      return newBet;
      
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
  },

  /**
   * Resolução da Aposta e Devolução do Prêmio
   */
  async settle(id, status, result, closing_odd = null) {
    if (!['won', 'lost', 'void', 'push'].includes(status)) {
      throw new AppError('Status de settlement inválido', 400);
    }

    const client = await getClient();
    try {
      await client.query('BEGIN');
      await client.query('SELECT pg_advisory_xact_lock(1)');

      const { rows: betRows } = await client.query('SELECT * FROM bets WHERE id = $1 FOR UPDATE', [id]);
      if (!betRows.length) throw new AppError('Bet não encontrada', 404);
      const bet = betRows[0];

      if (bet.status !== 'open') {
        throw new AppError(`Bet já resolvida (${bet.status})`, 400, 'ALREADY_SETTLED');
      }

      // Calcula profit_loss
      const stake = parseFloat(bet.stake);
      let profit_loss = 0;
      let clv = null;
      let toBankrollOp = null;
      let bankrollValue = 0;

      // CLV Calculation if closing odds informed: (odd_placed / closing_odd - 1) * 100
      if (closing_odd) {
        clv = ((bet.odd_placed / closing_odd) - 1) * 100;
      }

      if (status === 'won') {
        profit_loss = parseFloat(bet.potential_return) - stake;
        toBankrollOp = 'win';
        bankrollValue = parseFloat(bet.potential_return); // Devolve o stake + profit
      } else if (status === 'lost') {
        profit_loss = -stake;
        // Não adiciona no bankroll pois 'perdemos' e o dinheiro já foi sacado no open (betting)
      } else if (status === 'void' || status === 'push') {
        profit_loss = 0;
        toBankrollOp = 'win'; // Refunding the exact amount logic is add
        bankrollValue = stake;
      }

      // Update the Bet row
      const updateSql = `
        UPDATE bets SET 
          status = $1, result = $2, profit_loss = $3, closing_odd = $4, clv = $5, settled_at = NOW()
        WHERE id = $6 RETURNING *
      `;
      const updatedBetRes = await client.query(updateSql, [status, result, profit_loss, closing_odd, clv, id]);
      
      // Update Bankroll ONLY if returning funds (won/void/push)
      if (toBankrollOp && bankrollValue > 0) {
        await Bankroll.addEntry({
          operation: toBankrollOp,
          amount: bankrollValue,
          bet_id: bet.id,
          description: `Settled Bet #${bet.id} as ${status}`
        }, client);
      }

      await client.query('COMMIT');
      return updatedBetRes.rows[0];

    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
  },

  async getStats(filters = {}) {
    // Calculo geral para a dashboard de roi real (bets executadas)
    const { rows } = await query(`
      SELECT 
        COUNT(*) as total_bets,
        SUM(stake) as total_staked,
        SUM(profit_loss) as total_profit,
        (SUM(profit_loss) / SUM(stake)) * 100 as roi_pct,
        SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END)::decimal / NULLIF(COUNT(*) FILTER (WHERE status IN ('won', 'lost')), 0) * 100 as hit_rate_pct,
        AVG(clv) as avg_clv
      FROM bets
      WHERE status != 'open'
    `);
    return rows[0];
  }
};

module.exports = Bet;
