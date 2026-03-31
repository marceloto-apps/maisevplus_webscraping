const TeamStatsAgg = require('../models/TeamStatsAgg');
const MatchStats = require('../models/MatchStats');
const { query } = require('../config/database');
const AppError = require('../utils/AppError');

class StatsService {
  async recalculateTeamStats(teamId, leagueId, season) {
    // Dispara a agregação base das CTEs do Postgres (goals, xg, etc)
    const baseAgg = await TeamStatsAgg.recalculate(teamId, leagueId, season);
    
    if (!baseAgg) return null;

    // Resolução do TODO da Fase 3: Completar Form_last5 e afins via lógica local
    const formLast5 = await this.calculateForm(teamId, 5);
    
    // Atualiza o resultado mesclando local business rules (ex: form) c/ a CTE
    const updated = await TeamStatsAgg.upsert({
      ...baseAgg,
      form_last5: formLast5,
    });
    
    return updated;
  }

  calculateElo(teamA, teamB, result, kFactor = 20) {
    // result rating = 1 para Win, 0.5 para Draw, 0 para Loss
    const expectedA = 1 / (1 + Math.pow(10, (teamB - teamA) / 400));
    const newEloA = teamA + kFactor * (result - expectedA);
    const newEloB = teamB + kFactor * ((1 - result) - (1 - expectedA));
    
    return { newEloA, newEloB };
  }

  async calculateForm(teamId, limit = 5) {
    const teamIdInt = parseInt(teamId, 10);
    // String form: WWDLW (Left=recentes)
    const sql = `
      SELECT home_score, away_score, home_team_id 
      FROM matches 
      WHERE status = 'finished' AND (home_team_id = $1 OR away_team_id = $1)
        AND home_score IS NOT NULL AND away_score IS NOT NULL
      ORDER BY match_date DESC LIMIT $2
    `;
    const { rows } = await query(sql, [teamIdInt, limit]);
    
    let formString = '';
    for (const m of rows) {
      const isHome = m.home_team_id === teamIdInt;
      if (m.home_score === m.away_score) formString += 'D';
      else if (isHome && m.home_score > m.away_score) formString += 'W';
      else if (!isHome && m.away_score > m.home_score) formString += 'W';
      else formString += 'L';
    }
    
    return formString; 
  }

  factorial(n) {
    if (n <= 1) return 1;
    let result = 1;
    for (let i = 2; i <= n; i++) result *= i;
    return result;
  }

  poisson(k, lambda) {
    return (Math.pow(lambda, k) * Math.exp(-lambda)) / this.factorial(k);
  }

  getPoissonProbabilities(lambdaHome, lambdaAway, maxGoals = 6) {
    const matrix = [];
    for (let i = 0; i <= maxGoals; i++) { // Home
      matrix[i] = [];
      for (let j = 0; j <= maxGoals; j++) { // Away
        matrix[i][j] = this.poisson(i, lambdaHome) * this.poisson(j, lambdaAway);
      }
    }
    return matrix;
  }

  /**
   * Implementação Preditiva Matemática (Modelo Zero / Baseline)
   * Extraindo o xG Agregado de cada equipa e calculando O/U, 1x2 e BTTS
   */
  async predictMatch(matchId) {
    const { rows: matchRows } = await query(`SELECT * FROM matches WHERE id = $1`, [matchId]);
    if (!matchRows.length) throw new AppError('Partida nao encontrada', 404);
    const match = matchRows[0];

    const hStats = await TeamStatsAgg.findByTeam(match.home_team_id, match.season);
    const aStats = await TeamStatsAgg.findByTeam(match.away_team_id, match.season);

    if (!hStats || !aStats || hStats.matches_played < 3 || aStats.matches_played < 3) {
      throw new AppError('Amostragem estatistica pregressa insuficiente p/ rodar o modelo de Poisson', 400);
    }

    // Baseline Poisson (Usando Gols em caso de falha no xG) + Modificador Mandante Basico 10%
    // TODO (v1.1): Evoluir o lambda cruzando força ofensiva vs defensiva adv (xg_against) e média da liga (Dixon-Coles)
    const lambdaHome = (parseFloat(hStats.xg_for) || parseFloat(hStats.goals_for)) / (parseFloat(hStats.matches_played) || 1) * 1.1; 
    const lambdaAway = (parseFloat(aStats.xg_for) || parseFloat(aStats.goals_for)) / (parseFloat(aStats.matches_played) || 1);

    const maxGoals = 8;
    const matrix = this.getPoissonProbabilities(lambdaHome, lambdaAway, maxGoals);

    let prob1 = 0, probX = 0, prob2 = 0;
    let probOver25 = 0;
    let probBttsYes = 0;

    for (let h = 0; h <= maxGoals; h++) {
      for (let a = 0; a <= maxGoals; a++) {
        const prob = matrix[h][a];
        
        if (h > a) prob1 += prob;
        else if (h === a) probX += prob;
        else prob2 += prob;

        if (h + a > 2.5) probOver25 += prob;
        if (h > 0 && a > 0) probBttsYes += prob;
      }
    }

    // Ao inves de varar até o infinito, truncamos em Max Goals(8) e normalizamos pra dar exatos 100% de probabilidade do frame:
    const norm1X2 = prob1 + probX + prob2;

    return {
      match_id: match.id,
      model_name: "MaisEV_Poisson_v1",
      model_version: "1.0",
      confidence: "medium", // Pode ser atrelado ao número de samples/rodadas
      markets: {
        "1X2": {
          "1": prob1 / norm1X2,
          "X": probX / norm1X2,
          "2": prob2 / norm1X2
        },
        "over_under_2.5": {
          "over": probOver25,
          "under": 1 - probOver25
        },
        "btts": {
          "yes": probBttsYes,
          "no": 1 - probBttsYes
        }
      }
    };
  }
}

module.exports = new StatsService();
