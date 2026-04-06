"""
T04 — src/db/logger.py
Logger central estruturado em JSON (timestamps ISO, levels, source).
Usa structlog como backend para integração com Docker logs e PM2.
"""

import logging
import os
import structlog


def configure_logging() -> None:
    """
    Configura o pipeline de logging estruturado.
    Chamar uma vez, no entry-point do scheduler/scraper.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(source: str) -> structlog.BoundLogger:
    """
    Retorna um logger vinculado ao nome da fonte (ex: 'footystats', 'flashscore').
    Uso: logger = get_logger(__name__)
    """
    return structlog.get_logger(source)
