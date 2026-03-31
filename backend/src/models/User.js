const bcrypt = require('bcrypt');
const { query } = require('../config/database');

const User = {
  async findById(id) {
    const { rows } = await query('SELECT id, username, email, role, active, created_at, updated_at FROM users WHERE id = $1', [id]);
    return rows[0] || null;
  },

  async findByUsername(username) {
    const { rows } = await query('SELECT * FROM users WHERE username = $1', [username]);
    return rows[0] || null;
  },

  async findByEmail(email) {
    const { rows } = await query('SELECT * FROM users WHERE email = $1', [email]);
    return rows[0] || null;
  },

  async create(data) {
    const { username, email, password, role = 'user' } = data;
    const passwordHash = await bcrypt.hash(password, 10);
    const { rows } = await query(
      `INSERT INTO users (username, email, password_hash, role, active)
       VALUES ($1, $2, $3, $4, $5)
       RETURNING id, username, email, role, active, created_at`,
      [username, email, passwordHash, role, true]
    );
    return rows[0];
  },

  async validatePassword(plainText, hash) {
    return await bcrypt.compare(plainText, hash);
  }
};

module.exports = User;
