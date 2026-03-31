const express = require('express');
const router = express.Router();
const Joi = require('joi');
const { Team, TeamStatsAgg } = require('../models');
const footystatsService = require('../services/footystats');
const { authenticate, authorize } = require('../middlewares/auth');
const { validate } = require('../middlewares/validate');
const AppError = require('../utils/AppError');
const parseId = require('../utils/parseId');

router.use(authenticate);

const filterSchema = Joi.object({
  country: Joi.string().optional(),
  active: Joi.boolean().optional(),
  league_id: Joi.number().integer().optional()
});

router.get('/', validate(filterSchema, 'query'), async (req, res, next) => {
  try {
    const teams = await Team.findAll(req.query);
    res.json(teams);
  } catch (error) {
    next(error);
  }
});

router.get('/:id', async (req, res, next) => {
  try {
    const id = parseId(req.params.id, 'ID de equipe');
    const team = await Team.findById(id);
    if (!team) throw new AppError('Equipe não encontrada no banco', 404);
    
    // Injeca um aglomerado da season base nas infos brutas da equipe
    const season = req.query.season ? parseId(req.query.season, 'Season') : null;
    const stats = season ? await TeamStatsAgg.findByTeam(id, season) : null;
    
    res.json({ ...team, stats});
  } catch (error) {
    next(error);
  }
});

const syncSchema = Joi.object({
  season_id: Joi.number().optional()
});

/**
 * Sync Admin. Precisa puxar teams de contextos de LIGAS (league_id no parametro da rota)
 */
router.post('/sync/:leagueId', authorize('admin'), validate(syncSchema, 'body'), async (req, res, next) => {
  let fsData = [];
  const syncedCount = { total: 0, inserted: 0 };
  try {
    const leagueId = parseId(req.params.leagueId, 'leagueId');
    fsData = await footystatsService.fetchTeams(leagueId, req.body.season_id);
    syncedCount.total = fsData.length;
    
    for (const item of fsData) {
      const data = {
        name: item.name,
        country: item.country,
        footystats_id: item.id,
        logo_url: item.image,
        active: true
      };
      await Team.upsertByFootystatsId(data);
      syncedCount.inserted++;
    }

    res.json({ success: true, details: `Equipes da liga ${leagueId} sincronizadas. Updated: ${syncedCount.inserted}.` });
  } catch (error) {
    if (syncedCount.total > 0) {
      error.message = `Sync parcial: ${syncedCount.inserted}/${syncedCount.total} concluídos. ${error.message}`;
    }
    next(error);
  }
});

module.exports = router;
