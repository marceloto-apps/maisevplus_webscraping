const axios = require('axios');
const config = require('../config');
const logger = require('../config/logger');

// Artificial delay for avoiding rate-limits
const sleep = ms => new Promise(r => setTimeout(r, ms));

class FootystatsService {
  constructor() {
    this.key = config.apis.footystats.key;
    this.client = axios.create({
      baseURL: config.apis.footystats.baseUrl,
      timeout: 15000,
    });
  }

  buildUrl(endpoint, params = {}) {
    const query = new URLSearchParams({ key: this.key, ...params }).toString();
    return `${endpoint}?${query}`;
  }

  async _requestWithRateLimit(url) {
    if (!this.key || this.key === 'SUA_CHAVE_AQUI') {
       logger.error('FOOTYSTATS_API_KEY não configurada no .env');
       throw new Error('Missing FOOTYSTATS_API_KEY');
    }

    try {
      logger.info(`Chamando API FootyStats: ${url.split('key=')[0]}...`);
      const response = await this.client.get(url);
      
      // Documentação FootyStats geralmente pede 1req por segundo para contas standard
      await sleep(1000);

      const data = response.data;
      if (!data.success) {
        throw new Error(`A API FootyStats retornou erro: ${data.msg || 'Unknown'}`);
      }
      return data.data;

    } catch (error) {
      logger.error('Falha na comunicação HTTP com FootyStats:', error.message);
      throw error;
    }
  }

  async fetchLeagues(season_id) {
    const params = season_id ? { chosen_season_id: season_id } : {};
    const url = this.buildUrl('/league-list', params);
    return this._requestWithRateLimit(url);
  }

  async fetchTeams(leagueId, season_id = null) {
    const params = { chosen_season_id: season_id || leagueId }; 
    const url = this.buildUrl('/league-teams', params);
    return this._requestWithRateLimit(url);
  }

  async fetchMatches(leagueId, season_id = null) {
    const params = { chosen_season_id: season_id || leagueId };
    const url = this.buildUrl('/league-matches', params);
    return this._requestWithRateLimit(url);
  }

  async fetchMatchDetails(matchId) {
    const params = { match_id: matchId };
    const url = this.buildUrl('/match', params);
    return this._requestWithRateLimit(url);
  }
}

module.exports = new FootystatsService();
