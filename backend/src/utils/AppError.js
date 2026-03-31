class AppError extends Error {
  constructor(message, statusCode = 500, code = 'INTERNAL_ERROR', details = null) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
    this.isOperational = true; // ← é isso que ativa o tratamento correto no errorHandler
    Error.captureStackTrace(this, this.constructor);
  }
}

module.exports = AppError;
