const cron = require('node-cron');
const logger = require('../config/logger');
const settlementService = require('../services/settlementService');

const tasks = [];

const startJobs = () => {
  logger.info('Iniciando Orchestrator de Cron Jobs...');

  let isRunning = false;

  const settlementTask = cron.schedule('5 * * * *', async () => {
    if (isRunning) {
      logger.warn('[CRON] Settlement anterior ainda em execução. Pulando esta rodada.');
      return;
    }

    isRunning = true;
    logger.info('[CRON] Iniciando rotina automática de Settlement para Partidas Finalizadas...');

    try {
      const results = await settlementService.runSettlement();
      logger.info(`[CRON] Settlement Concluído! Bets: ${results?.betsSettled || 0} | Predictions: ${results?.predictionsSettled || 0}.`);
    } catch (error) {
      logger.error(`[CRON] Falha Crítica ao tentar rodar o Settlement: ${error.message}`, { stack: error.stack });
    } finally {
      isRunning = false;
    }
  });

  tasks.push(settlementTask);
};

const stopJobs = () => {
  tasks.forEach(t => t.stop());
  logger.info('[CRON] Todos os jobs parados.');
};

module.exports = { startJobs, stopJobs };
