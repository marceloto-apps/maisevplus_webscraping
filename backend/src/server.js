const app = require('./app');
const config = require('./config');
const logger = require('./config/logger');
const { startJobs, stopJobs } = require('./jobs/scheduler');

const PORT = config.port || 3000;

const server = app.listen(PORT, () => {
  logger.info(`Motor MaisEV+ ativo na porta ${PORT} [${process.env.NODE_ENV || 'development'}]`);
  if (process.env.NODE_ENV !== 'test') {
    startJobs();
  }
});

const shutdown = async (signal) => {
  logger.info(`${signal} recebido. Encerrando gracefully...`);
  stopJobs();
  server.close(() => {
    logger.info('HTTP server fechado de forma limpa.');
    process.exit(0);
  });
  
  // Fallback se conexões em hold agarrarem o fechamento após 10s
  setTimeout(() => {
    logger.error('Shutdown deadline atingido (10s), forçando fechamento do processo.');
    process.exit(1);
  }, 10000);
};

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
