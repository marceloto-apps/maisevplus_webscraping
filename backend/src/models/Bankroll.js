const { query, getClient } = require('../config/database');
const AppError = require('../utils/AppError');

const Bankroll = {
  /**
   * Pega o saldo mais recente
   */
  async getCurrentBalance() {
    const { rows } = await query('SELECT balance FROM bankroll ORDER BY created_at DESC LIMIT 1');
    return rows.length ? parseFloat(rows[0].balance) : 0;
  },

  async getHistory(limit = 50) {
    const { rows } = await query('SELECT * FROM bankroll ORDER BY created_at DESC LIMIT $1', [limit]);
    return rows;
  },

  /**
   * addEntry usa transação isolada ou externa (se passar o client)
   * Usa advisory lock para evitar race conditions em processamento concorrente de apostas
   */
  async addEntry(data, externalClient = null) {
    if (externalClient) {
      return this._executeEntry(data, externalClient);
    }

    const client = await getClient();
    try {
      await client.query('BEGIN');
      
      // Lock advisory para serializar escritas no bankroll (chave 1 arbitraria para bankroll)
      await client.query('SELECT pg_advisory_xact_lock(1)');

      const result = await this._executeEntry(data, client);

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
  async _executeEntry(data, client) {
    const { rows: latest } = await client.query(
      'SELECT balance FROM bankroll ORDER BY created_at DESC LIMIT 1 FOR UPDATE'
    );
    const currentBalance = latest.length ? parseFloat(latest[0].balance) : 0;

    const { operation, amount, bet_id = null, description = '' } = data;
    const parsedAmount = parseFloat(amount);

    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      throw new AppError('Valor deve ser positivo', 400, 'INVALID_AMOUNT');
    }

    let newBalance;
    if (operation === 'deposit' || operation === 'win') {
      newBalance = currentBalance + parsedAmount;
    } else if (operation === 'withdraw' || operation === 'bet' || operation === 'loss') {
      newBalance = currentBalance - parsedAmount;
    } else {
      throw new AppError('Operação de bankroll inválida', 400, 'INVALID_OPERATION');
    }

    if (newBalance < 0 && operation !== 'deposit') {
      throw new AppError('Saldo insuficiente para esta operação', 400, 'INSUFFICIENT_FUNDS');
    }

    const { rows } = await client.query(
      `INSERT INTO bankroll (balance, operation, amount, bet_id, description, created_at)
       VALUES ($1, $2, $3, $4, $5, NOW())
       RETURNING *`,
      [newBalance, operation, parsedAmount, bet_id, description]
    );

    return rows[0];
  },

  async deposit(amount, description = 'Deposit via API') {
    return this.addEntry({ operation: 'deposit', amount, description });
  },

  async withdraw(amount, description = 'Withdraw via API') {
    return this.addEntry({ operation: 'withdraw', amount, description });
  }
};

module.exports = Bankroll;
