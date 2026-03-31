const Bet = require('../models/Bet');
const Prediction = require('../models/Prediction');
const Odds = require('../models/Odds');
const { query } = require('../config/database');
const AppError = require('../utils/AppError');

class SettlementService {
  /**
   * Resolve o PNL de uma string de mercado baseado no placar real
   */
  checkMarketResult(market, selection, homeScore, awayScore) {
    if (homeScore === null || awayScore === null) return null;

    let hs = parseInt(homeScore, 10);
    let as = parseInt(awayScore, 10);

    if (market === '1X2') {
      if (hs > as && selection === '1') return 'won';
      if (hs === as && selection === 'X') return 'won';
      if (hs < as && selection === '2') return 'won';
      return 'lost';
    }

    // Suportando string dinâmica over_under_2.5 
    if (market.startsWith('over_under_')) {
      const line = parseFloat(market.replace('over_under_', ''));
      const total = hs + as;
      if (total === line) return 'push';
      if (selection === 'over') return total > line ? 'won' : 'lost';
      if (selection === 'under') return total < line ? 'won' : 'lost';
    }

    if (market === 'btts') {
      const isBtts = hs > 0 && as > 0;
      if (selection === 'yes') return isBtts ? 'won' : 'lost';
      if (selection === 'no') return !isBtts ? 'won' : 'lost';
    }

    // Se a lógica da Selection não tá pronta aqui (ex Handicap), skipa.
    return null;
  }

  /**
   * Aplica o check em TODAS as apostas de uma partida consolidada 
   */
  async settleMatch(matchId) {
    const { rows: matchRows } = await query('SELECT * FROM matches WHERE id = $1', [matchId]);
    if (!matchRows.length) return false;

    const match = matchRows[0];
    if (match.status !== 'finished' || match.home_score === null || match.away_score === null) return false;

    // 1) Predictions/Model ROI Virtual 
    const { rows: pendingPreds } = await query("SELECT * FROM predictions WHERE match_id = $1 AND status = 'pending'", [matchId]);

    for (const pred of pendingPreds) {
      const resultStatus = this.checkMarketResult(pred.market, pred.selection, match.home_score, match.away_score);
      if (resultStatus) {
        // Enfiamos o placar stringificado em result no Model para logging 
        await Prediction.updateStatus(pred.id, resultStatus, `${match.home_score}-${match.away_score}`);
      }
    }

    // 2) Dinheiro de Verdade (Bets Reais vs Bankroll)
    const { rows: openBets } = await query("SELECT * FROM bets WHERE match_id = $1 AND status = 'open'", [matchId]);
    
    // Busca closing odds se existirem para o match
    const closingOdds = await Odds.getClosingByMatch(matchId);
    
    for (const b of openBets) {
      const betStatus = this.checkMarketResult(b.market, b.selection, match.home_score, match.away_score);
      
      const matchedClosing = closingOdds.find(o => o.market === b.market && o.selection === b.selection);
      const closingOdd = matchedClosing ? parseFloat(matchedClosing.odd_value) : null;
      
      if (betStatus) {
        // O `Bet.settle` já aciona o Bankroll.addEntry com lock advisory internamente
        await Bet.settle(b.id, betStatus, `${match.home_score}-${match.away_score}`, closingOdd);
      }
    }

    return true;
  }

  /**
   * Varredilha de Orfanato (Resolve passivos pra trás)
   */
  async runSettlement() {
    const sql = `
        SELECT DISTINCT m.id 
        FROM matches m
        JOIN bets b ON m.id = b.match_id
        WHERE m.status = 'finished' AND b.status = 'open' 
          AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
      `;
    const { rows } = await query(sql);
    let resolvedCount = 0;

    for (const row of rows) {
      await this.settleMatch(row.id);
      resolvedCount++;
    }

    // (Opcional) Faz a batida isolada só pra Predictions pendentes pra compilar o ROI Virtual do modelo sem bet
    const sqlPreds = `
        SELECT DISTINCT m.id 
        FROM matches m
        JOIN predictions p ON m.id = p.match_id
        WHERE m.status = 'finished' AND p.status = 'pending'
          AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
      `;
    const { rows: predRows } = await query(sqlPreds);

    let predOnlyCount = 0;
    const settledMatchIds = new Set(rows.map(r => r.id));

    for (const r of predRows) {
      // Ignora as q já passaram na varredura da Bet
      if (!settledMatchIds.has(r.id)) {
        await this.settleMatch(r.id);
        predOnlyCount++;
      }
    }

    return { betsSettled: resolvedCount, predictionsSettled: predOnlyCount };
  }
}

module.exports = new SettlementService();
