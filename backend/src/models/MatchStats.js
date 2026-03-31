const { query } = require('../config/database');

const MatchStats = {
  async findByMatchId(matchId) {
    const { rows } = await query('SELECT * FROM match_stats WHERE match_id = $1 ORDER BY is_home DESC', [matchId]);
    return rows;
  },

  async create(data) {
    const {
      match_id, team_id, is_home, possession, shots_total, shots_on_target,
      corners, fouls, yellow_cards, red_cards, offsides, xg,
      xg_first_half, xg_second_half, dangerous_attacks, attacks, ppda
    } = data;

    const { rows } = await query(
      `INSERT INTO match_stats (
        match_id, team_id, is_home, possession, shots_total, shots_on_target,
        corners, fouls, yellow_cards, red_cards, offsides, xg,
        xg_first_half, xg_second_half, dangerous_attacks, attacks, ppda
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
      RETURNING *`,
      [
        match_id, team_id, is_home, possession, shots_total, shots_on_target,
        corners, fouls, yellow_cards, red_cards, offsides, xg,
        xg_first_half, xg_second_half, dangerous_attacks, attacks, ppda
      ]
    );
    return rows[0];
  },

  async upsert(data) {
    const {
      match_id, team_id, is_home, possession, shots_total, shots_on_target,
      corners, fouls, yellow_cards, red_cards, offsides, xg,
      xg_first_half, xg_second_half, dangerous_attacks, attacks, ppda
    } = data;

    const { rows } = await query(
      `INSERT INTO match_stats (
        match_id, team_id, is_home, possession, shots_total, shots_on_target,
        corners, fouls, yellow_cards, red_cards, offsides, xg,
        xg_first_half, xg_second_half, dangerous_attacks, attacks, ppda
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
      ON CONFLICT (match_id, team_id) DO UPDATE SET
        is_home = EXCLUDED.is_home,
        possession = EXCLUDED.possession,
        shots_total = EXCLUDED.shots_total,
        shots_on_target = EXCLUDED.shots_on_target,
        corners = EXCLUDED.corners,
        fouls = EXCLUDED.fouls,
        yellow_cards = EXCLUDED.yellow_cards,
        red_cards = EXCLUDED.red_cards,
        offsides = EXCLUDED.offsides,
        xg = EXCLUDED.xg,
        xg_first_half = EXCLUDED.xg_first_half,
        xg_second_half = EXCLUDED.xg_second_half,
        dangerous_attacks = EXCLUDED.dangerous_attacks,
        attacks = EXCLUDED.attacks,
        ppda = EXCLUDED.ppda
      RETURNING *`,
      [
        match_id, team_id, is_home, possession, shots_total, shots_on_target,
        corners, fouls, yellow_cards, red_cards, offsides, xg,
        xg_first_half, xg_second_half, dangerous_attacks, attacks, ppda
      ]
    );
    return rows[0];
  }
};

module.exports = MatchStats;
