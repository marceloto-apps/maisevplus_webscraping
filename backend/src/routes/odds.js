const express = require('express');
const router = express.Router();
const Joi = require('joi');
const { Odds } = require('../models');
const { authenticate } = require('../middlewares/auth');
const { validate } = require('../middlewares/validate');
const AppError = require('../utils/AppError');

router.use(authenticate);

const qsSchema = Joi.object({
  market: Joi.string().optional(),
  bookmaker: Joi.string().optional()
});

router.get('/match/:matchId', validate(qsSchema, 'query'), async (req, res, next) => {
  try {
    const id = parseInt(req.params.matchId, 10);
    if (isNaN(id)) throw new AppError('matchId inválido', 400);

    const oddsLogs = await Odds.findByMatchId(id, req.query);
    
    res.json(oddsLogs);
  } catch (error) {
    next(error);
  }
});

const qsMovieSchema = Joi.object({
  market: Joi.string().required(),
  selection: Joi.string().required()
});

// Movement Tracking p/ graficos lineares no front:
router.get('/movement/:matchId', validate(qsMovieSchema, 'query'), async (req, res, next) => {
  try {
    const id = parseInt(req.params.matchId, 10);
    if (isNaN(id)) throw new AppError('matchId inválido', 400);

    const { market, selection } = req.query;
    
    const lines = await Odds.getOddsMovement(id, market, selection);
    
    res.json(lines);
  } catch (error) {
    next(error);
  }
});

module.exports = router;
