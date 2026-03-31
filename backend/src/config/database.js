const { Pool } = require('pg');
const config = require('./index');

const pool = new Pool({
  connectionString: config.db.url,
  max: config.db.maxConnections,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
});

pool.on('error', (err) => {
  console.error('[DB] Erro inesperado no pool:', err.message);
});

const query = async (text, params) => {
  const start = Date.now();
  const res = await pool.query(text, params);
  const duration = Date.now() - start;
  if (process.env.NODE_ENV !== 'production') {
    console.log('[DB] Query executada', { text: text.substring(0, 80), duration: `${duration}ms`, rows: res.rowCount });
  }
  return res;
};

const getClient = async () => {
  const client = await pool.connect();
  return client;
};

const testConnection = async () => {
  try {
    const res = await pool.query('SELECT NOW() AS now, current_database() AS db');
    console.log(`[DB] Conectado a "${res.rows[0].db}" em ${res.rows[0].now}`);
    return true;
  } catch (err) {
    console.error('[DB] Falha na conexão:', err.message);
    return false;
  }
};

module.exports = { pool, query, getClient, testConnection };
