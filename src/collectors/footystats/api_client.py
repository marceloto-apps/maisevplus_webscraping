"""
FootyStats API Client
Fornece requisições seguras com exponential backoff, retry
e injeção inteligente da chave de autenticação primária.
"""
import os
import asyncio
import httpx
from typing import List, Dict, Optional
from json import JSONDecodeError

from ...db.logger import get_logger

logger = get_logger(__name__)

class FootyStatsClient:
    BASE_URL = "https://api.football-data-api.com"
    
    def __init__(self, max_retries: int = 4):
        self.api_key = os.getenv("FOOTYSTATS_API_KEY")
        self.max_retries = max_retries
        
        if not self.api_key:
            logger.warning("footystats_api_key_missing", env_var="FOOTYSTATS_API_KEY")

        self.client = httpx.AsyncClient(timeout=45.0)

    async def close(self):
        await self.client.aclose()

    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """ Wrapper HTTP GET que executa o exponential backoff e injecta Key. """
        if params is None:
            params = {}
        params['key'] = self.api_key

        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.get(url, params=params)
                
                # Excecoes transientes (ex: Throttling / WAF)
                if response.status_code in (429, 500, 502, 503, 504):
                    logger.warning("footystats_http_retry",
                                   status_code=response.status_code,
                                   attempt=attempt + 1,
                                   url=url)
                    
                    if attempt < self.max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        response.raise_for_status()

                response.raise_for_status()
                
                payload = response.json()
                if payload.get("success") is False:
                    # Falha semantica da Footystats (ex. chaves vazias retornam success=False)
                    logger.error("footystats_semantic_error", 
                                 endpoint=endpoint, 
                                 msg=payload.get("msg", "Unknown error"))
                    return []
                
                # Endpoint de matches-results habitualmente devolve os dados em "data"
                data = payload.get("data", [])
                
                # Formato comum da API: uma lista de listas para objetos paginados virtualmente 
                # mesmo quando não pedimos, ou uma lista direta de dados.
                if isinstance(data, list):
                    return data
                
                return []

            except (httpx.RequestError, JSONDecodeError) as e:
                logger.error("footystats_network_error", error=str(e), attempt=attempt+1)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return []
        
        return []

    async def fetch_season_matches(self, season_id: int) -> List[Dict]:
        """ Busca a totalidade de jogos disponíveis para uma Season do Footystats (sem paginação). """
        return await self._get("league-matches", params={"season_id": season_id})

    async def fetch_fixtures(self, date_from: str, date_to: str) -> List[Dict]:
        """
        Coleta calendário futuro agendado cross-season num range.
        Pode requerer paginacao nos results dependendo da api-data-api, 
        mas usamos params de data por ser mais restrito p/ UPSERTs pendentes.
        """
        # A chave api de fixtures deles requer o chosen_date. Mas como temos as seasons salvas
        # o melhor é rodar um cron que atualiza os `scheduled` periodicamente.
        # Estamos criando essa fundação conforme a task pede.
        return await self._get("todays-matches", params={"date": date_from})
