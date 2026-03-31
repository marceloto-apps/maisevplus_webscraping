const express = require('express');
const helmet = require('helmet');
const cors = require('cors');
const rateLimit = require('express-rate-limit');
const config = require('./config');
const logger = require('./config/logger');
const routes = require('./routes');

const app = express();

// Defesas de Borda e Payload Parsers
app.use(helmet());
app.use(cors({
  origin: config.corsOrigins || ['http://localhost:5173'],
  credentials: true
}));
app.use(express.json({ limit: '10kb' }));

// Liveness Probe para Docker Healthcheck
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Rate Limiting Global e Específico
const globalLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 Minutos de janela
  max: 500, // Limite conservador para API
  message: { status: 'error', message: 'Muitas requisições deste IP. Hold the payload e tente novamente mais tarde.' }
});

app.use('/api', globalLimiter);

// Bind de todas as Endpoints da Fase 5
app.use('/api', routes);

// NotFound Fallback
app.use((req, res, next) => {
  res.status(404).json({ status: 'error', message: 'Endpoint não disponível no cluster.' });
});

// Master Error Handler / Interceptor Global
app.use((err, req, res, next) => {
  // Delega loggign para o Winston Tracker (files/console)
  logger.error(`[App Express] ${err.message}`, { stack: err.stack, details: err.details });

  // Exposição tipada de Joi Validator
  if (err.isJoi) {
    return res.status(400).json({
      status: 'error',
      code: 'VALIDATION_ERROR',
      message: err.details[0] ? err.details[0].message : err.message,
    });
  }

  // Propagação de AppError operacionais (400, 401, 403, 404, etc)
  if (err.isOperational) {
    return res.status(err.statusCode || 400).json({
      status: 'error',
      code: err.code || 'OPERATIONAL_ERROR',
      message: err.message,
      details: err.details || null
    });
  }

  // Obfuscação de Stack Trace de 500 puro
  return res.status(500).json({
    status: 'error',
    code: 'INTERNAL_SERVER_ERROR',
    message: 'Um colapso imprevisto ocorreu no Core Engine.'
  });
});

module.exports = app;
