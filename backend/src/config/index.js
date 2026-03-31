require('dotenv').config();

// Validação visual simples para startup fail-fast
const requiredEnvVars = ['DATABASE_URL', 'JWT_SECRET'];
for (const envVar of requiredEnvVars) {
  if (!process.env[envVar]) {
    console.error(`[CONFIG ERROR] Variável de ambiente obrigatória não definida: ${envVar}`);
    process.exit(1);
  }
}

const config = {
  env: process.env.NODE_ENV || 'development',
  corsOrigins: process.env.CORS_ORIGINS
    ? process.env.CORS_ORIGINS.split(',').map(s => s.trim())
    : ['http://localhost:5173'],
  server: {
    port: parseInt(process.env.PORT, 10) || 3000,
  },
  db: {
    url: process.env.DATABASE_URL,
    maxConnections: parseInt(process.env.DB_MAX_CONNECTIONS, 10) || 20,
  },
  jwt: {
    secret: process.env.JWT_SECRET,
    expiresIn: process.env.JWT_EXPIRES_IN || '24h',
  },
  apis: {
    footystats: {
      key: process.env.FOOTYSTATS_API_KEY,
      baseUrl: 'https://api.football-data-api.com',
    },
    oddsApi: {
      key: process.env.ODDS_API_KEY,
    },
  },
  rateLimit: {
    windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS, 10) || 900000, // default 15 mins
    max: parseInt(process.env.RATE_LIMIT_MAX, 10) || 100,
  },
  log: {
    level: process.env.LOG_LEVEL || 'info',
    dir: process.env.LOG_DIR,
  }
};

module.exports = config;
