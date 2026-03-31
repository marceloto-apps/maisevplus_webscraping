const express = require('express');
const router = express.Router();
const Joi = require('joi');
const { Match, Team } = require('../models');
const footystatsService = require('../services/footystats');
const settlementService = require('../services/settlementService');
const { authenticate, authorize } = require('../middlewares/auth');
const { validate } = require('../middlewares/validate');
const AppError = require('../utils/AppError');
const parseId = require('../utils/parseId');

router.use(authenticate);

const querySchema = Joi.object({
  league_id: Joi.number().integer(),
  status: Joi.string().valid('scheduled', 'live', 'finished', 'postponed'),
  date_from: Joi.date().iso(),
  date_to: Joi.date().iso(),
  team_id: Joi.number().integer(),
  limit: Joi.number().min(1).max(200).default(50),
  offset: Joi.number().min(0).default(0)
});

router.get('/', validate(querySchema, 'query'), async (req, res, next) => {
  try {
    const matches = await Match.findAll(req.query);
    res.json(matches);
  } catch (error) {
    next(error);
  }
});

const upcomingSchema = Joi.object({
  days: Joi.number().integer().min(1).max(30).default(7)
});

router.get('/upcoming', validate(upcomingSchema, 'query'), async (req, res, next) => {
  try {
    const { days } = req.query;
    const matches = await Match.findUpcoming(days);
    res.json(matches);
  } catch (error) {
    next(error);
  }
});

router.get('/:id', async (req, res, next) => {
  try {
    const id = parseId(req.params.id, 'ID de partida');
    const matchRaw = await Match.findById(id);
    if (!matchRaw) throw new AppError('Partida não encontrada', 404);
    
    res.json(matchRaw);
  } catch (error) {
    next(error);
  }
});

const syncSchema = Joi.object({
  season_id: Joi.number().optional()
});

/**
 * Sync Footystats API - League context
 */
router.post('/sync/:leagueId', authorize('admin'), validate(syncSchema, 'body'), async (req, res, next) => {
  let dataFs = [];
  const syncedCount = { total: 0, inserted: 0 };
  const skipped = [];
  
  try {
    const leagueId = parseId(req.params.leagueId, 'leagueId');
    const { season_id } = req.body;
    dataFs = await footystatsService.fetchMatches(leagueId, season_id);
    syncedCount.total = dataFs.length;

    // Pré-carrega todos os teams da liga no map p/ evitar N+2 queries (O(1) lookups)
    const allLeagueTeams = await Team.findAll({ league_id: leagueId });
    const teamMap = new Map();
    for (const t of allLeagueTeams) {
      teamMap.set(t.footystats_id, t.id);
    }

    for (const item of dataFs) {
      const homeTeamId = teamMap.get(item.homeID);
      const awayTeamId = teamMap.get(item.awayID);
      
      if (!homeTeamId || !awayTeamId) {
         skipped.push({
           footystats_id: item.id,
           reason: `Team não mapeado: home=${item.homeID}(PG:${!!homeTeamId}), away=${item.awayID}(PG:${!!awayTeamId})`
         });
         continue; 
      }
      
      const row = {
        league_id: leagueId, 
        home_team_id: homeTeamId,      
        away_team_id: awayTeamId,
        match_date: new Date(item.date_unix * 1000).toISOString(),
        status: item.status, 
        home_score: item.homeGoalCount,
        away_score: item.awayGoalCount,
        ht_home_score: item.ht_goals_team_a,
        ht_away_score: item.ht_goals_team_b,
        footystats_id: item.id,
        season: item.season,
        round: item.game_week
      };
      
      await Match.upsertByFootystatsId(row);
      syncedCount.inserted++;
    }
    
    res.json({ 
      success: true, 
      message: `Partidas Sincronizadas: ${syncedCount.inserted}/${syncedCount.total}`,
      skipped_count: skipped.length,
      skipped: skipped.slice(0, 20)
    });
  } catch (error) {
    if (syncedCount.total > 0) {
      error.message = `Sync parcial: ${syncedCount.inserted}/${syncedCount.total} concluídos. ${error.message}`;
    }
    next(error);
  }
});

const forceSettleSchema = Joi.object({
  homeScore: Joi.number().integer().min(0).optional(),
  awayScore: Joi.number().integer().min(0).optional()
}).and('homeScore', 'awayScore');

/**
 * Admins Forçam a resolução (Settlement) manual de uma Partida já finalizada
 */
router.post('/:id/settle', authorize('admin'), validate(forceSettleSchema, 'body'), async (req, res, next) => {
  try {
    const id = parseId(req.params.id, 'ID de partida');

    if (req.body.homeScore !== undefined && req.body.awayScore !== undefined) {
      await Match.updateResult(id, req.body.homeScore, req.body.awayScore);
    }

    const checkReturn = await settlementService.settleMatch(id);
    
    if (!checkReturn) {
      throw new AppError('A partida não reúne as condições base para settlement (Não Finished ou sem Placar)', 400);
    }
    
    res.json({ success: true, message: `Match #${id} resolvido comercialmente com sucesso.` });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
