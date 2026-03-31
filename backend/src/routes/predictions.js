const express = require('express');
const router = express.Router();
const Joi = require('joi');
const { Prediction, Odds } = require('../models');
const statsService = require('../services/statsService');
const { getClient } = require('../config/database');
const { authenticate, authorize } = require('../middlewares/auth');
const { validate } = require('../middlewares/validate');
const AppError = require('../utils/AppError');

router.use(authenticate);

const qsSchema = Joi.object({
  status: Joi.string().valid('pending', 'won', 'lost', 'push', 'void'),
  model_name: Joi.string(),
  market: Joi.string(),
  min_ev: Joi.number().min(0),
  date_from: Joi.date().iso(),
  date_to: Joi.date().iso(),
  limit: Joi.number().min(1).max(200).default(50),
  offset: Joi.number().min(0).default(0)
});

router.get('/', validate(qsSchema, 'query'), async (req, res, next) => {
  try {
    const preds = await Prediction.findAll(req.query);
    res.json(preds);
  } catch (error) {
    next(error);
  }
});

router.get('/value-bets', async (req, res, next) => {
  try {
    // Para value bets ativas globais de hoje, varreríamos uma cache ou rodaríamos findValueBets() 
    // em todos os matches scheduled.
    // Mas p/ simplificação de rota da spec, listamos preds pendentes ordenadas por EV
    // (o q não cruza real time best_odds de ODD_HISTORY a todo segundo a menos q montemos um Worker)
    const threshold = parseFloat(req.query.min_ev) || 2.0;

    const queryFilters = {
      status: 'pending',
      min_ev: threshold,
      limit: 100
    };
    
    // Devolve da cache do DB os calculos já persistidos pelas pipelines
    const preds = await Prediction.findAll(queryFilters);
    res.json(preds);
  } catch (error) {
    next(error);
  }
});

router.get('/performance', async (req, res, next) => {
  try {
    const stats = await Prediction.getPerformanceStats(req.query);
    res.json(stats);
  } catch (error) {
    next(error);
  }
});

// Admin Route: Triggers the execution of Poisson Modeling + Storage 
router.post('/generate/:matchId', authorize('admin'), async (req, res, next) => {
  const client = await getClient();
  let transactionStarted = false;
  try {
    const id = parseInt(req.params.matchId, 10);
    if (isNaN(id)) throw new AppError('matchId inválido', 400);

    // Calc poisson e geracao do bundle preditivo
    const resultMatrix = await statsService.predictMatch(id);
    const latestOdds = await Odds.getLatestByMatch(id);
    
    // O service devolve um dicionario multi dimensionado das probs
    // O processo agora cria N predictions no DB iterando de forma transacional
    const createdArray = [];
    
    await client.query('BEGIN');
    transactionStarted = true;
    
    for (const [market, schemaProps] of Object.entries(resultMatrix.markets)) {
      for (const [selection, impliedProbVal] of Object.entries(schemaProps)) {
         
         const matchedOdd = latestOdds.find(o => o.market === market && o.selection === selection);
         const bestOdd = matchedOdd ? parseFloat(matchedOdd.odd_value) : 1.0; 
         // Se cair no fallback de 1.0 ele gera EV negativo, portanto não vira value bet por padrão (seguro).
         const bookmaker = matchedOdd ? matchedOdd.bookmaker : 'System_Init';

         const persistData = {
           match_id: id,
           model_name: resultMatrix.model_name,
           model_version: resultMatrix.model_version,
           market, 
           selection,
           predicted_prob: impliedProbVal,
           best_odd_available: bestOdd,
           bookmaker: bookmaker,
           confidence: resultMatrix.confidence
         };
         
         const pRow = await Prediction.createWithClient(client, persistData);
         createdArray.push(pRow);
      }
    }
    
    await client.query('COMMIT');

    res.json({ success: true, count: createdArray.length, generated: createdArray });
  } catch (error) {
    if (transactionStarted) await client.query('ROLLBACK');
    next(error);
  } finally {
    client.release();
  }
});

module.exports = router;
