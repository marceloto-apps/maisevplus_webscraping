const Odds = require('../models/Odds');
const Prediction = require('../models/Prediction');

class OddsService {
  calculateImpliedProbability(odd) {
    if (odd <= 1) return 0;
    return 1 / odd;
  }

  /**
   * Remove o Vig/Margin de uma casa de aposta usando normalização proporcional
   * @param {Array<Number>} odds Array de odds de um mercado exato (ex: [home, draw, away])
   * @returns {Array<Number>} Array contendo as probabilidades purificadas/justas
   */
  removeVig(odds) {
    if (!odds || !odds.length) return [];
    
    let totalImpliedProb = 0;
    const probs = odds.map(num => {
      const p = this.calculateImpliedProbability(num);
      totalImpliedProb += p;
      return p;
    });

    if (totalImpliedProb === 0) return [];

    // Desvigar = Probabilidade Individual / Somatória das Implied Probs (que excede 100%)
    return probs.map(p => p / totalImpliedProb);
  }

  /**
   * EV em Base Centesimal (Retorno percentual sobre capital investido)
   * Fórmula: ((Odd * Prob) - 1) * 100
   */
  calculateEV(predictedProb, oddValue) {
    return ((oddValue * predictedProb) - 1) * 100;
  }

  /**
   * Closing Line Value (%)
   * Retorna em quão melhor a linha "Placed" vence a de Fechamento do game.
   */
  calculateCLV(oddPlaced, closingOdd) {
    if (!closingOdd || closingOdd <= 1) return 0;
    return ((oddPlaced / closingOdd) - 1) * 100;
  }

  /**
   * Cruza TODAS as Previsões salvas contra TODAS as Odds das casas.
   * Emite alertas em formato de Value Bet real para serem exibidas em tela.
   */
  async findValueBets(matchId, thresholdPct = 2) {
    const availableOdds = await Odds.getLatestByMatch(matchId);
    if (!availableOdds.length) return [];

    const predictions = await Prediction.findByMatchId(matchId);
    if (!predictions.length) return [];

    const valueBets = [];

    for (const pred of predictions) {
      // Coleta todas as odds abertas para o mercado e selection que o bot simulou
      const marketOdds = availableOdds.filter(o => 
        o.market === pred.market && 
        o.selection === pred.selection
      );
      
      let bestOdd = null;
      for (const odd of marketOdds) {
        if (!bestOdd || parseFloat(odd.odd_value) > parseFloat(bestOdd.odd_value)) {
          bestOdd = odd;
        }
      }

      if (bestOdd) {
        const ev = this.calculateEV(parseFloat(pred.predicted_prob), parseFloat(bestOdd.odd_value));
        
        if (ev >= thresholdPct) {
          valueBets.push({
            prediction_id: pred.id,
            market: pred.market,
            selection: pred.selection,
            best_odd: parseFloat(bestOdd.odd_value),
            bookmaker: bestOdd.bookmaker,
            predicted_prob: parseFloat(pred.predicted_prob),
            ev_pct: parseFloat(ev.toFixed(2))
          });
        }
      }
    }

    return valueBets.sort((a, b) => b.ev_pct - a.ev_pct);
  }
}

module.exports = new OddsService();
