const Prediction = require('../models/Prediction');
const Bankroll = require('../models/Bankroll');
const AppError = require('../utils/AppError');

class KellyService {
  /**
   * Calcula fração Kelly completa pura baseada na matemática
   * Fórmula: f = (bp - q) / b
   * @param {Number} prob Probabilidade modelada verdadeira (0 a 1)
   * @param {Number} odd Odd Decimal disponível 
   */
  fullKelly(prob, odd) {
    if (odd <= 1 || prob <= 0) return 0;
    
    const b = odd - 1;       // Retorno líquido potencial (odds em payout)
    const q = 1 - prob;      // Probabilidade de errar
    
    // Fracao calculada da banca inteira protegida pra n dar infinito
    const k = (b * prob - q) / b;
    return Math.max(0, k); // Nunca recomende valores de apostas negativos
  }

  /**
   * Calcula o Fractional Kelly limitando risco global de quebra da variância
   * Standard Default = 0.25 (Quarter Kelly)
   */
  fractionalKelly(prob, odd, fraction = 0.25) {
    const baseKelly = this.fullKelly(prob, odd);
    return baseKelly * fraction;
  }

  /**
   * Clampa (amassa) a formatação real de banca pra injetar na tela UI como quantia
   * Multiplica a conta real da banca em R$ (balance) x a Fração Fractional e delimita
   */
  calculateStake(bankrollBalance, kellyFraction, minStake = 2.00, maxStake = 1000.00) {
    if (kellyFraction <= 0) return 0;
    if (bankrollBalance <= 0) return 0;

    let targetStake = bankrollBalance * kellyFraction;

    // Constrain by absolute floor bounds and house roofs
    if (targetStake < minStake) targetStake = minStake;
    if (targetStake > maxStake) targetStake = maxStake;

    return parseFloat(targetStake.toFixed(2));
  }

  /**
   * Helper direto. Descobre o target em R$ de uma entry do Prediction id
   */
  async getRecommendedStake(predictionId, fractionMode = 0.25, betLimit = 500) {
    const pred = await Prediction.findById(predictionId);
    if (!pred) throw new AppError('Predição inexistente', 404);

    if (pred.ev_pct <= 0) return 0;

    const balance = await Bankroll.getCurrentBalance();
    if (balance <= 0) return 0;

    const bestKelly = this.fractionalKelly(
      parseFloat(pred.predicted_prob), 
      parseFloat(pred.best_odd_available), 
      fractionMode
    );

    return this.calculateStake(balance, bestKelly, 2.0, betLimit);
  }
}

module.exports = new KellyService();
