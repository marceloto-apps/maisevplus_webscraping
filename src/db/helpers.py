"""
T04 — src/db/helpers.py
Helpers de banco de dados: queries parametrizadas e log de ingestão.

Contrato do log_ingestion:
  - log_ingestion_start()  → insere com status='running', retorna log_id
  - log_ingestion_end()    → atualiza finished_at + métricas (sempre chamado
                             mesmo em caso de erro, para não perder visibilidade
                             de jobs que crasharam no meio)
"""

import asyncpg
from datetime import datetime, timezone
from typing import Any, Optional
from .pool import get_pool
from .logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers genéricos
# ---------------------------------------------------------------------------

async def fetch_val(query: str, *args: Any) -> Any:
    """Retorna um único valor escalar (ex: COUNT, MAX)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


async def fetch_one(query: str, *args: Any) -> Optional[asyncpg.Record]:
    """Retorna uma única linha ou None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetch_all(query: str, *args: Any) -> list[asyncpg.Record]:
    """Retorna todas as linhas correspondentes."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def execute(query: str, *args: Any) -> str:
    """Executa um statement sem retornar linhas (INSERT, UPDATE, DELETE)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


async def execute_many(query: str, args_list: list[tuple]) -> None:
    """Executa um statement em lote (ex: INSERT de múltiplos registros)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.executemany(query, args_list)


# ---------------------------------------------------------------------------
# Logging de Ingestão — contrato de duas chamadas
# ---------------------------------------------------------------------------

async def log_ingestion_start(
    *,
    job_id: str,
    source: str,
    job_type: str,
    started_at: Optional[datetime] = None,
    metadata: Optional[dict] = None,
) -> int:
    """
    Insere um registro na ingestion_log com status='running'.
    Retorna o log_id gerado para ser passado ao log_ingestion_end().
    """
    started_at = started_at or datetime.now(timezone.utc)
    import json
    metadata_json = json.dumps(metadata) if metadata else None

    log_id: int = await fetch_val(
        """
        INSERT INTO ingestion_log
            (job_id, source, job_type, started_at, status, metadata_json)
        VALUES ($1, $2, $3, $4, 'running', $5::jsonb)
        RETURNING log_id
        """,
        job_id, source, job_type, started_at, metadata_json,
    )
    logger.info("ingestion_started", job_id=job_id, source=source, log_id=log_id)
    return log_id


async def log_ingestion_end(
    log_id: int,
    *,
    status: str,
    records_collected: int = 0,
    records_new: int = 0,
    records_skipped: int = 0,
    error_message: Optional[str] = None,
    finished_at: Optional[datetime] = None,
) -> None:
    """
    Atualiza o registro de ingestion_log com o resultado final do job.
    status deve ser: 'success' | 'partial' | 'failed'
    Sempre chamar — mesmo em blocos except — para não perder jobs crashed.
    """
    finished_at = finished_at or datetime.now(timezone.utc)

    await execute(
        """
        UPDATE ingestion_log
        SET
            finished_at       = $1,
            status            = $2,
            records_collected = $3,
            records_new       = $4,
            records_skipped   = $5,
            error_message     = $6
        WHERE log_id = $7
        """,
        finished_at, status,
        records_collected, records_new, records_skipped,
        error_message, log_id,
    )
    logger.info(
        "ingestion_ended",
        log_id=log_id,
        status=status,
        records_new=records_new,
        records_skipped=records_skipped,
    )
