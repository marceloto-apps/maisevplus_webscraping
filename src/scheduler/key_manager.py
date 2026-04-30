"""
KeyManager — rotação multi-key.
"""
from typing import Optional
from src.db import helpers
from src.db.logger import get_logger

logger = get_logger(__name__)

class NoKeysAvailableError(Exception):
    pass

class KeyManager:
    _alerted_keys: set[int] = set()
    @classmethod
    async def get_key(cls, service: str, requests_needed: int = 1) -> str:
        """
        Retorna a chave disponível para o serviço, priorizando a de menor uso
        e que ainda tenha limite. Atualiza o uso no ato.
        """
        query = """
            UPDATE api_keys
            SET usage_today = COALESCE(usage_today, 0) + $2,
                usage_month = COALESCE(usage_month, 0) + $2,
                last_used_at = NOW()
            WHERE key_id = (
                SELECT key_id FROM api_keys
                WHERE service = $1 AND is_active = TRUE
                  AND (limit_daily IS NULL OR COALESCE(usage_today, 0) + $2 <= limit_daily)
                  AND (limit_monthly IS NULL OR COALESCE(usage_month, 0) + $2 <= limit_monthly)
                ORDER BY COALESCE(usage_today, 0) ASC, COALESCE(usage_month, 0) ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING key_value, key_id, usage_today, limit_daily
        """
        row = await helpers.fetch_one(query, service, requests_needed)
        
        if not row:
            logger.error("no_keys_available", service=service)
            raise NoKeysAvailableError(f"Sem chaves ativas ou com limite suficiente para {service}")
            
        key_id = row['key_id']
        key_value = row['key_value']
        
        limit_daily = row['limit_daily']
        usage_today = row['usage_today']
        
        if limit_daily and limit_daily > 0:
            usage_pct = usage_today / limit_daily
            if usage_pct >= 0.8 and key_id not in cls._alerted_keys:
                cls._alerted_keys.add(key_id)
                logger.warning("key_approaching_daily_limit", service=service, key_id=key_id, usage_pct=round(usage_pct, 2))

        logger.info("key_allocated", service=service, key_id=key_id, requests=requests_needed)
        return key_value

    @staticmethod
    async def get_service_budget(service: str) -> dict:
        """
        Retorna o agrupamento de budget total e restante por serviço.
        """
        query = """
            SELECT 
                SUM(limit_daily) as total_limit_daily,
                SUM(COALESCE(usage_today, 0)) as total_usage_today,
                SUM(limit_monthly) as total_limit_monthly,
                SUM(COALESCE(usage_month, 0)) as total_usage_month
            FROM api_keys
            WHERE service = $1 AND is_active = TRUE
        """
        row = await helpers.fetch_one(query, service)
        return {
            "total_limit_daily": row['total_limit_daily'] or 0,
            "total_usage_today": row['total_usage_today'] or 0,
            "total_limit_monthly": row['total_limit_monthly'] or 0,
            "total_usage_month": row['total_usage_month'] or 0,
        }

    @classmethod
    async def reset_daily(cls) -> None:
        """Reseta usage_today para todas as keys ativas e limpa o set de alertas."""
        query = "UPDATE api_keys SET usage_today = 0 WHERE is_active = TRUE;"
        await helpers.execute(query)
        cls._alerted_keys.clear()
        logger.info("keys_reset_daily")

    @staticmethod
    async def reset_monthly() -> None:
        """Reseta usage_month para todas as keys ativas."""
        query = "UPDATE api_keys SET usage_month = 0 WHERE is_active = TRUE;"
        await helpers.execute(query)
        logger.info("keys_reset_monthly")
