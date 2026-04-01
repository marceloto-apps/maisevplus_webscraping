const { query, getClient } = require('../config/database');
const AppError = require('../utils/AppError');

const Bankroll = {
  /**
   * Pega o saldo mais recente do usuário
   */
  async getCurrentBalance(userId) {
    if (!userId) throw new Error('user_id required for getCurrentBalance');
    const { rows } = await query(
      'SELECT balance_after FROM bankroll WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1', 
      [userId]
    );
    return rows.length ? parseFloat(rows[0].balance_after) : 0;
  },

  async getHistory(userId, limit = 50) {
    if (!userId) throw new Error('user_id required for getHistory');
    const { rows } = await query(
      'SELECT * FROM bankroll WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2', 
      [userId, limit]
    );
    return rows;
  },

  /**
   * addEntry usa transação isolada ou externa (se passar o client)
   * Usa advisory lock isolado pelo ID do usuário
   */
  async addEntry(userId, data, externalClient = null) {
    if (!userId) throw new Error('user_id required for addEntry');
    if (externalClient) {
      return this._executeEntry(userId, data, externalClient);
    }

    const client = await getClient();
    try {
      await client.query('BEGIN');
      
      // Lock advisory atrelado ao usuário em vez de global
      await client.query('SELECT pg_advisory_xact_lock($1)', [userId]);

      const result = await this._executeEntry(userId, data, client);

      await client.query('COMMIT');
      return result;
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
  },

  /** Lógica pura isolada — sempre roda dentro de uma transação */
  async _executeEntry(userId, data, client) {
    const { rows: latest } = await client.query(
      'SELECT balance_after FROM bankroll WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1 FOR UPDATE',
      [userId]
    );
    const currentBalance = latest.length ? parseFloat(latest[0].balance_after) : 0;

    const { tx_type, amount, bet_id = null, description = '' } = data;
    const parsedAmount = parseFloat(amount);

    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      throw new AppError('Valor deve ser positivo', 400, 'INVALID_AMOUNT');
    }

    let newBalance;
    if (tx_type === 'deposit' || tx_type === 'bet_won' || tx_type === 'bet_void' || tx_type === 'adjustment') {
      newBalance = currentBalance + parsedAmount;
    } else if (tx_type === 'withdraw' || tx_type === 'bet_placed' || tx_type === 'bet_lost') {
      newBalance = currentBalance - parsedAmount;
    } else {
      throw new AppError('Operação de bankroll inválida', 400, 'INVALID_OPERATION');
    }

    if (newBalance < 0 && tx_type !== 'deposit') {
      throw new AppError('Saldo insuficiente para esta operação', 400, 'INSUFFICIENT_FUNDS');
    }

    const { rows } = await client.query(
      `INSERT INTO bankroll (user_id, balance_after, tx_type, amount, bet_id, description, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, NOW())
       RETURNING *`,
      [userId, newBalance, tx_type, parsedAmount, bet_id, description]
    );

    return rows[0];
  },

  async deposit(userId, amount, description = 'Deposit via API') {
    return this.addEntry(userId, { tx_type: 'deposit', amount, description });
  },

  async withdraw(userId, amount, description = 'Withdraw via API') {
    return this.addEntry(userId, { tx_type: 'withdraw', amount, description });
  }
};

module.exports = Bankroll;
