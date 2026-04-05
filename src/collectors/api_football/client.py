"""
ApiFootballClient — Wrapper HTTP resiliente com rate limiting rígido e rotação de key.
Cumpre a Fase 2 (Passo 3) do plano de engenharia de ingestão.
"""

import asyncio
import time
from typing import Optional
import httpx
from src.scheduler.key_manager import KeyManager
from src.db.logger import get_logger

logger = get_logger(__name__)

class ApiFootballClient:
    """
    Cliente centralizado para a API-Football.
    Garante o rate limit de 10 requests / minuto em toda a aplicação via Window Lock estrito.
    """
    _lock = asyncio.Lock()
    _request_times = []
    
    BASE_URL = "https://v3.football.api-sports.io"
    RATE_LIMIT_PER_MINUTE = 300
    
    @classmethod
    async def _wait_for_rate_limit(cls):
        """
        Bloqueia a execução se o limite de requisições no último minuto foi atingido.
        """
        async with cls._lock:
            now = time.time()
            
            # Limpa timestamps mais antigos que 60.5 segundos (buffer extra de segurança)
            cls._request_times = [t for t in cls._request_times if now - t < 60.5]
            
            if len(cls._request_times) >= cls.RATE_LIMIT_PER_MINUTE:
                # Necessário esperar até a requisição mais antiga da janela sair
                oldest_request = cls._request_times[0]
                sleep_time = 60.5 - (now - oldest_request)
                
                if sleep_time > 0:
                    logger.debug("api_football_rate_limit_wait", seconds=round(sleep_time, 2))
                    await asyncio.sleep(sleep_time)
                
                # Recalcula o tempo após o sleep
                now = time.time()
                cls._request_times = [t for t in cls._request_times if now - t < 60.5]
            
            cls._request_times.append(now)

    @classmethod
    async def get(cls, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        Executa um GET assegurando: limitador de taxa (10 rpm), rotação passiva pelo KeyManager
        e retries assíncronos.
        """
        await cls._wait_for_rate_limit()
        
        # Pega a chave ativa com saldo (KeyManager atualiza db_usage atomicamente)
        api_key = await KeyManager.get_key("api_football", requests_needed=1)
        
        headers = {
            "x-apisports-key": api_key
        }
        
        url = f"{cls.BASE_URL}{endpoint}"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            max_retries = 3
            for retry in range(max_retries):
                try:
                    response = await client.get(url, headers=headers, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        errors = data.get("errors")
                        
                        if errors:
                            if isinstance(errors, dict) and "requests" in errors:
                                logger.error("api_football_limit_reached_on_call", endpoint=endpoint, errors=errors)
                                raise Exception(f"Quota Excedida: {errors}")
                            elif isinstance(errors, dict) and "rateLimit" in errors:
                                logger.warning("api_football_rate_limit_hit_from_api", retry=retry)
                                await asyncio.sleep(6.5)
                                continue
                            else:
                                raise Exception(f"Erros na API: {errors}")
                                
                        return data.get("response", [])
                        
                    elif response.status_code == 429: # Too Many Requests
                        logger.warning("api_football_429_received", retry=retry)
                        await asyncio.sleep(7.0)
                        
                    elif response.status_code >= 500:
                        logger.warning("api_football_500_error", status=response.status_code, retry=retry)
                        await asyncio.sleep(2.0 * (retry + 1))
                        
                    else:
                        response.raise_for_status()
                        
                except httpx.RequestError as e:
                    logger.warning("api_football_request_error", error=str(e), retry=retry)
                    await asyncio.sleep(2.0)
                    if retry == max_retries - 1:
                        raise e
            
            raise Exception("Máximo de retentativas excedido na ApiFootballClient")
