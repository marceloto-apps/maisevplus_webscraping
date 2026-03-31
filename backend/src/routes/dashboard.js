const express = require('express');
const router = express.Router();
const { query } = require('../config/database');
const { authenticate } = require('../middlewares/auth');
const { Bankroll } = require('../models');

router.use(authenticate);

/**
 * Retorna os KPIs primordiais para o Header do React / Next.js
 * (Saldo, Bets Abertas count, Lucro/Preju meses, etc)
 */
router.get('/summary', async (req, res, next) => {
  try {
    const [
      balance,
      { rows: openBetsRows },
      { rows: monthlyPnlRows }
    ] = await Promise.all([
      Bankroll.getCurrentBalance(),
      query(`SELECT COUNT(*)::int AS count, COALESCE(SUM(stake), 0) AS exposure FROM bets WHERE status = 'open'`),
      query(`
        SELECT COALESCE(SUM(profit_loss), 0) AS monthly_pnl 
        FROM bets 
        WHERE status IN ('won', 'lost', 'void', 'push') 
          AND settled_at >= date_trunc('month', CURRENT_DATE)
      `)
    ]);

    res.json({
      current_balance: parseFloat(balance) || 0,
      open_bets_count: openBetsRows[0].count,
      open_exposure: parseFloat(openBetsRows[0].exposure),
      monthly_pnl: parseFloat(monthlyPnlRows[0].monthly_pnl)
    });
  } catch (error) {
    next(error);
  }
});

router.get('/daily-pnl', async (req, res, next) => {
  try {
    // Últimos 30 dias com generate_series para cobrir lacunas
    const sql = `
      SELECT 
        d::date AS day,
        COALESCE(SUM(b.profit_loss), 0) AS daily_pnl
      FROM generate_series(
        CURRENT_DATE - INTERVAL '30 days', 
        CURRENT_DATE, 
        '1 day'
      ) d
      LEFT JOIN bets b 
        ON date_trunc('day', b.settled_at)::date = d::date
        AND b.status IN ('won', 'lost', 'void', 'push')
      GROUP BY 1
      ORDER BY 1 ASC
    `;
    const { rows } = await query(sql);
    
    // Tratamento para arrays plain no react (Chart.js / Recharts)
    const formatted = rows.map(r => ({
      date: r.day,
      pnl: parseFloat(r.daily_pnl)
    }));
    
    res.json(formatted);
  } catch (error) {
    next(error);
  }
});

router.get('/model-performance', async (req, res, next) => {
  try {
    const sql = `
      SELECT 
        p.model_name,
        COUNT(p.id) AS total_pred_settled,
        SUM(CASE WHEN p.result_status = 'won' THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN p.result_status = 'lost' THEN 1 ELSE 0 END) AS losses,
        SUM(CASE WHEN p.result_status = 'push' THEN 1 ELSE 0 END) AS pushes,
        COALESCE(SUM(b.profit_loss), 0) AS total_profit,
        COALESCE(SUM(b.stake), 0) AS total_staked
      FROM predictions p
      LEFT JOIN bets b ON p.id = b.prediction_id
      WHERE p.result_status IN ('won', 'lost', 'push')
      GROUP BY p.model_name
    `;
    const { rows } = await query(sql);

    const format = rows.map(r => {
      const w = parseInt(r.wins, 10);
      const l = parseInt(r.losses, 10);
      const p = parseInt(r.pushes, 10);
      const total = w + l; // winrate normally excludes pushes
      const profit = parseFloat(r.total_profit);
      const staked = parseFloat(r.total_staked);
      const roi = staked > 0 ? (profit / staked) * 100 : 0;

      return {
        model_name: r.model_name,
        win_rate: total > 0 ? parseFloat((w / total * 100).toFixed(2)) : 0,
        samples: parseInt(r.total_pred_settled, 10),
        roi_pct: parseFloat(roi.toFixed(2))
      };
    });

    res.json(format);
  } catch (error) {
    next(error);
  }
});

module.exports = router;
