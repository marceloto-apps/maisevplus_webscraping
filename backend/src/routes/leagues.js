const express = require('express');
const router = express.Router();
const Joi = require('joi');
const { League } = require('../models');
const footystatsService = require('../services/footystats');
const { authenticate, authorize } = require('../middlewares/auth');
const { validate } = require('../middlewares/validate');
const AppError = require('../utils/AppError');
const parseId = require('../utils/parseId');

// Todas as rotas de ligas exigem autenticação
router.use(authenticate);

const filterSchema = Joi.object({
  country: Joi.string().optional(),
  active: Joi.boolean().optional(),
});

router.get('/', validate(filterSchema, 'query'), async (req, res, next) => {
  try {
    const filters = req.query;
    const leagues = await League.findAll(filters);
    res.json(leagues);
  } catch (error) {
    next(error);
  }
});

router.get('/:id', async (req, res, next) => {
  try {
    const id = parseId(req.params.id, 'ID de liga');
    const league = await League.findById(id);
    if (!league) throw new AppError('Liga não encontrada', 404);
    
    res.json(league);
  } catch (error) {
    next(error);
  }
});

const syncSchema = Joi.object({
  season_id: Joi.number().optional()
});

/**
 * Route ADMIN - Trigger externo que baixa as Ligas ativas da API da FS
 * e realiza o UPSERT completo mantendo id do PG limpo.
 */
router.post('/sync', authorize('admin'), validate(syncSchema, 'body'), async (req, res, next) => {
  let fsData = [];
  const syncedCount = { total: 0, updated: 0 };
  
  try {
    fsData = await footystatsService.fetchLeagues(req.body.season_id);
    syncedCount.total = fsData.length;
    
    for (const item of fsData) {
      const data = {
        name: item.name,
        country: item.country,
        footystats_id: item.id, // O FootyStats manda season_id e ID geral como id da season context.
        season: item.season,
        tier: item.format || 3,
        active: true
      };
      
      await League.upsertByFootystatsId(data);
      syncedCount.updated++;
    }

    res.json({ success: true, message: `Sync concluído com sucesso. ${syncedCount.updated} Ligas afetadas.` });
  } catch (error) {
    if (syncedCount.total > 0) {
      error.message = `Sync parcial: ${syncedCount.updated}/${syncedCount.total} concluídos. ${error.message}`;
    }
    next(error);
  }
});

module.exports = router;
