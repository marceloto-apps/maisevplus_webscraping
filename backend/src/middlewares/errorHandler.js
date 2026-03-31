const logger = require('../config/logger');

/**
 * Middleware global do Express para intercepção e padronização de erros.
 * Garante o payload { error: { code, message, details } }
 */
const errorHandler = (err, req, res, next) => {
  logger.error(`Ocorreu um erro não tratado na rota ${req.method} ${req.originalUrl}:`, err);

  const statusCode = err.statusCode || err.status || 500;
  const isProduction = process.env.NODE_ENV === 'production';

  // Se já tem formato customizado de erro do nosso sistema
  if (err.isOperational) {
    return res.status(statusCode).json({
      error: {
        code: err.code || 'INTERNAL_ERROR',
        message: err.message,
        details: err.details || null
      }
    });
  }

  // Falhas inesperadas
  return res.status(statusCode).json({
    error: {
      code: 'INTERNAL_SERVER_ERROR',
      message: isProduction ? 'Ocorreu um erro interno no servidor.' : err.message,
      // Não vazar stack trace em produção
      details: isProduction ? null : err.stack
    }
  });
};

module.exports = errorHandler;
