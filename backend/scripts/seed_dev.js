/**
 * seed_dev.js - Injeta dados falsos para viabilizar testes no M2 (Docker)
 * SEM PRECISAR RODAR OS SCRAPERS M1.
 */

const { pool } = require('../src/config/database');
const bcrypt = require('bcryptjs');
const crypto = require('crypto');

async function runSeed() {
  if (process.env.NODE_ENV === 'production') {
    console.error("🔴 ERRO CRÍTICO: Tentativa de rodar Seed de Dev em PRODUÇÃO. Abortando.");
    process.exit(1);
  }

  const client = await pool.connect();
  try {
    console.log("🌱 Iniciando Seed de Desenvolvimento (Idempotente)...");
    await client.query('BEGIN');

    // 1. Usuário Admin (Senha: 123456)
    const salt = await bcrypt.genSalt(10);
    const passwordHash = await bcrypt.hash('123456', salt);

    const { rows: users } = await client.query(`
      INSERT INTO users (username, email, password_hash, role)
      VALUES ('admin', 'admin@maisev.local', $1, 'admin')
      ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
      RETURNING id;
    `, [passwordHash]);
    const userId = users[0].id;
    console.log(`✅ Usuário admin garantido. (ID: ${userId})`);

    // 2. Mock de Banca ($10.000 se não existir histórico)
    const { rows: brCheck } = await client.query(
      `SELECT balance FROM bankroll ORDER BY created_at DESC LIMIT 1`
    );
    if (brCheck.length === 0) {
      await client.query(`
        INSERT INTO bankroll (balance, operation, amount, description, created_at)
        VALUES (10000.00, 'deposit', 10000.00, 'Seed Inicial de Dev', NOW());
      `);
      console.log(`✅ Banca falsa ativada ($ 10.000).`);
    }

    // 3. Liga e Season
    const { rows: leagues } = await client.query(`
      INSERT INTO leagues (code, name, country, season_format, tier)
      VALUES ('DEV_L1', 'Liga de Desenvolvimento', 'Localhost', 'aug_may', 1)
      ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
      RETURNING league_id;
    `);
    const leagueId = leagues[0].league_id;

    const { rows: seasons } = await client.query(`
      INSERT INTO seasons (league_id, label, start_date, footystats_season_id, is_current)
      VALUES ($1, '2024/2025', '2024-08-01', 99999, TRUE)
      ON CONFLICT (league_id, label) DO UPDATE SET footystats_season_id = EXCLUDED.footystats_season_id
      RETURNING season_id;
    `, [leagueId]);
    const seasonId = seasons[0].season_id;

    // 4. Bookmaker Fictícia
    const { rows: bookies } = await client.query(`
      INSERT INTO bookmakers (name, display_name, type, clv_priority)
      VALUES ('dev_bookie', 'Pinnacle DEV', 'sharp', 1)
      ON CONFLICT (name) DO UPDATE SET display_name = EXCLUDED.display_name
      RETURNING bookmaker_id;
    `);
    const bookmakerId = bookies[0].bookmaker_id;

    console.log(`✅ Liga, Season e Bookmaker garantidos.`);

    // 5. Times (4 mínimo para 2 partidas cruzadas)
    const teamNames = ['Dev United', 'Dev City', 'Dev Arsenal', 'Dev Chelsea'];
    const teamIds = [];
    for (const tName of teamNames) {
      const { rows: tCheck } = await client.query(
        `SELECT team_id FROM teams WHERE name_canonical = $1 LIMIT 1`, [tName]
      );
      if (tCheck.length > 0) {
        teamIds.push(tCheck[0].team_id);
      } else {
        const { rows: tInsert } = await client.query(
          `INSERT INTO teams (name_canonical, country) VALUES ($1, 'Localhost') RETURNING team_id`, [tName]
        );
        teamIds.push(tInsert[0].team_id);
      }
    }

    // 6. Matches + Odds + Predictions
    const games = [
      { home_id: teamIds[0], away_id: teamIds[1], status: 'scheduled', kickOff: new Date(Date.now() + 86400000).toISOString(), trueOdds: 1.85, bookieOdds: 2.10 },
      { home_id: teamIds[2], away_id: teamIds[3], status: 'finished', ft_home: 2, ft_away: 1, kickOff: new Date(Date.now() - 86400000).toISOString(), trueOdds: 2.05, bookieOdds: 1.95 }
    ];

    for (const g of games) {
      const { rows: mExist } = await client.query(`
        SELECT match_id FROM matches 
        WHERE league_id = $1 AND home_team_id = $2 AND away_team_id = $3
      `, [leagueId, g.home_id, g.away_id]);

      let matchId;
      if (mExist.length > 0) {
        matchId = mExist[0].match_id;
      } else {
        const { rows: mNew } = await client.query(`
          INSERT INTO matches (season_id, league_id, home_team_id, away_team_id, kickoff, status, ft_home, ft_away)
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
          RETURNING match_id;
        `, [seasonId, leagueId, g.home_id, g.away_id, g.kickOff, g.status, g.ft_home || null, g.ft_away || null]);
        matchId = mNew[0].match_id;

        const contentHash = crypto.createHash('sha256')
          .update(String(matchId) + Date.now().toString())
          .digest('hex');

        // Odds
        await client.query(`
          INSERT INTO odds_history (time, match_id, bookmaker_id, market_type, odds_1, odds_x, odds_2, overround, is_closing, source, content_hash)
          VALUES (NOW(), $1, $2, '1x2', $3, 3.40, 4.20, 1.02, TRUE, 'seed', $4)
        `, [matchId, bookmakerId, g.bookieOdds, contentHash]);

        // Prediction com EV
        const edge = ((1 / g.trueOdds) * g.bookieOdds) - 1;
        await client.query(`
          INSERT INTO predictions (match_id, market, selection, probability, true_odds, bookmaker_id, bookmaker_odds, edge, kelly_fraction, suggested_stake, status)
          VALUES ($1, '1x2', 'home', $2, $3, $4, $5, $6, 0.02, 200, 'open')
        `, [matchId, (1 / g.trueOdds), g.trueOdds, bookmakerId, g.bookieOdds, edge > 0 ? edge : 0]);
      }
    }

    console.log(`✅ Partidas, Odds e Predições garantidas.`);

    await client.query('COMMIT');
    console.log("🏁 Seed de Desenvolvimento concluído com SUCESSO!");
  } catch (err) {
    await client.query('ROLLBACK');
    console.error("❌ ERRO NO SEED:", err);
    throw err;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  const path = require('path');
  require('dotenv').config({ path: path.resolve(__dirname, '../../.env.docker') });
  runSeed()
    .then(() => process.exit(0))
    .catch(() => process.exit(1));
}

module.exports = runSeed;
