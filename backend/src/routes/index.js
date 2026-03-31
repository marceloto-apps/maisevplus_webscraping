const express = require('express');
const router = express.Router();

const authRoutes = require('./auth');
const leaguesRoutes = require('./leagues');
const teamsRoutes = require('./teams');
const matchesRoutes = require('./matches');
const oddsRoutes = require('./odds');
const predictionsRoutes = require('./predictions');
const betsRoutes = require('./bets');
const bankrollRoutes = require('./bankroll');
const dashboardRoutes = require('./dashboard');

router.use('/auth', authRoutes);
router.use('/leagues', leaguesRoutes);
router.use('/teams', teamsRoutes);
router.use('/matches', matchesRoutes);
router.use('/odds', oddsRoutes);
router.use('/predictions', predictionsRoutes);
router.use('/bets', betsRoutes);
router.use('/bankroll', bankrollRoutes);
router.use('/dashboard', dashboardRoutes);

module.exports = router;
