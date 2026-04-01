"""
T04 — src/db/pool.py
Pool de conexões asyncpg global e reutilizável por todos os collectors.
Tamanho do pool parametrizável via .env (DB_POOL_MIN, DB_POOL_MAX).
"""

import asyncpg
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Retorna o pool global, inicializando-o na primeira chamada."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=_build_dsn(),
            min_size=int(os.getenv("DB_POOL_MIN", "5")),
            max_size=int(os.getenv("DB_POOL_MAX", "20")),
            command_timeout=60,
            server_settings={"application_name": "maisev_scraper"},
        )
    return _pool


async def close_pool() -> None:
    """Fecha graciosamente o pool (chamar no shutdown do scheduler)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _build_dsn() -> str:
    """Monta a DSN a partir de DATABASE_URL ou variáveis individuais."""
    url = os.getenv("DATABASE_URL")
    if url:
        # asyncpg não aceita o prefixo 'postgresql+asyncpg://', normaliza
        return url.replace("postgresql+asyncpg://", "postgresql://")

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "maisevplus_db")
    user = os.getenv("DB_USER", "postgres")
    pwd  = os.getenv("DB_PASS", "")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{name}"
