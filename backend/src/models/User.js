const bcrypt = require('bcrypt');
const { query } = require('../config/database');

const User = {
  async findById(id) {
    const { rows } = await query('SELECT id, display_name, email, role, is_active, created_at, updated_at FROM users WHERE id = $1', [id]);
    return rows[0] || null;
  },

  async findByDisplayName(displayName) {
    const { rows } = await query('SELECT * FROM users WHERE display_name = $1', [displayName]);
    return rows[0] || null;
  },

  async findByEmail(email) {
    const { rows } = await query('SELECT * FROM users WHERE email = $1', [email]);
    return rows[0] || null;
  },

  async create(data) {
    const { display_name, email, password, role = 'user' } = data;
    const passwordHash = await bcrypt.hash(password, 10);
    const { rows } = await query(
      `INSERT INTO users (display_name, email, password_hash, role, is_active)
       VALUES ($1, $2, $3, $4, $5)
       RETURNING id, display_name, email, role, is_active, created_at`,
      [display_name, email, passwordHash, role, true]
    );
    return rows[0];
  },

  async validatePassword(plainText, hash) {
    return await bcrypt.compare(plainText, hash);
  }
};

module.exports = User;
