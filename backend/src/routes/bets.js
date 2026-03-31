const express = require('express');
const router = express.Router();
const Joi = require('joi');
const { Bet, Bankroll } = require('../models');
const { authenticate, authorize } = require('../middlewares/auth');
const { validate } = require('../middlewares/validate');
const AppError = require('../utils/AppError');

router.use(authenticate);

const qsSchema = Joi.object({
  status: Joi.string().valid('open', 'won', 'lost', 'push', 'void'),
  market: Joi.string(),
  date_from: Joi.date().iso(),
  date_to: Joi.date().iso(),
  limit: Joi.number().min(1).max(200).default(50),
  offset: Joi.number().min(0).default(0)
});

router.get('/', validate(qsSchema, 'query'), async (req, res, next) => {
  try {
    const bets = await Bet.findAll(req.query);
    res.json(bets);
  } catch (error) {
    next(error);
  }
});

router.get('/stats', validate(qsSchema, 'query'), async (req, res, next) => {
  try {
    const stats = await Bet.getStats(req.query);
    res.json(stats);
  } catch (error) {
    next(error);
  }
});

const createBetSchema = Joi.object({
  match_id: Joi.number().integer().required(),
  prediction_id: Joi.number().integer().optional(),
  bookmaker: Joi.string().required(),
  market: Joi.string().required(),
  selection: Joi.string().required(),
  odd: Joi.number().greater(1).required(),
  stake: Joi.number().positive().required()
});

router.post('/', validate(createBetSchema, 'body'), async (req, res, next) => {
  try {
    const betData = { ...req.body, user_id: req.user.id };
    
    // Validate balance before creating bet
    const balance = await Bankroll.getCurrentBalance();
    if (balance < betData.stake) {
      throw new AppError(`Saldo insuficiente. Bankroll: ${balance}, Stake: ${betData.stake}`, 400);
    }

    const { bet, bankrollEntry } = await Bet.create(betData);
    
    res.status(201).json({
      success: true,
      message: 'Aposta registrada com sucesso e saldo deduzido',
      bet,
      bankroll_entry: bankrollEntry
    });
  } catch (error) {
    next(error);
  }
});

const settleSchema = Joi.object({
  status: Joi.string().valid('won', 'lost', 'push', 'void').required(),
  result: Joi.string().max(255).optional(),
  closing_odd: Joi.number().greater(1).optional()
});

// Resolução pontual isolada (ex: operador validou via dashboard)
router.patch('/:id/settle', authorize('admin', 'operator'), validate(settleSchema, 'body'), async (req, res, next) => {
  try {
    const id = parseInt(req.params.id, 10);
    if (isNaN(id)) throw new AppError('ID de aposta inválido', 400);

    const { status, result, closing_odd } = req.body;

    const settledBet = await Bet.settle(id, status, result || null, closing_odd || null);
    
    res.json({
      success: true,
      message: `Aposta ${id} liquidada como ${status}. Lucros integrados na banca em tempo real.`,
      bet: settledBet
    });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
