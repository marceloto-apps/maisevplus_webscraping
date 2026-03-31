const express = require('express');
const router = express.Router();
const Joi = require('joi');
const { Bankroll } = require('../models');
const { authenticate, authorize } = require('../middlewares/auth');
const { validate } = require('../middlewares/validate');
const AppError = require('../utils/AppError');

router.use(authenticate);

router.get('/balance', async (req, res, next) => {
  try {
    const balance = await Bankroll.getCurrentBalance();
    res.json({ balance: Math.round(balance * 100) / 100 });
  } catch (error) {
    next(error);
  }
});

const histSchema = Joi.object({
  operation: Joi.string().valid('deposit', 'withdraw', 'bet', 'win', 'void', 'push'), // etc
  date_from: Joi.date().iso(),
  date_to: Joi.date().iso(),
  limit: Joi.number().min(1).max(200).default(50),
  offset: Joi.number().min(0).default(0)
});

router.get('/history', validate(histSchema, 'query'), async (req, res, next) => {
  try {
    const data = await Bankroll.getHistory(req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

const opSchema = Joi.object({
  amount: Joi.number().positive().required(),
  description: Joi.string().max(255).optional()
});

router.post('/deposit', authorize('admin'), validate(opSchema, 'body'), async (req, res, next) => {
  try {
    const { amount, description } = req.body;
    const entryData = {
      operation: 'deposit',
      amount: amount,
      description: description || 'Depósito manual'
    };
    
    const entry = await Bankroll.addEntry(entryData);
    res.status(201).json({ success: true, entry });
  } catch (error) {
    next(error);
  }
});

router.post('/withdraw', authorize('admin'), validate(opSchema, 'body'), async (req, res, next) => {
  try {
    const { amount, description } = req.body;
    
    // Front validation p/ UX
    const balance = await Bankroll.getCurrentBalance();
    if (amount > balance) {
      throw new AppError(`Saldo insuficiente para saque. Disponível: R$ ${balance}`, 400);
    }

    const entryData = {
      operation: 'withdraw',
      amount: amount, // A model converte withdraw pra negativo
      description: description || 'Saque manual'
    };
    
    const entry = await Bankroll.addEntry(entryData);
    res.status(201).json({ success: true, entry });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
