"""
Structured logging configuration using loguru.

Configures log format, levels, and sinks based on app settings.
Intercepts standard library logging to unify all log output.
"""

from __future__ import annotations

import logging
import sys

from loguru import logger

from services.ai_api.config import get_settings


class InterceptHandler(logging.Handler):
    """Redirect standard logging to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    """Configure application logging."""
    settings = get_settings()

    # Remove default loguru handler
    logger.remove()

    # Add stdout handler with structured format
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stdout,
        format=log_format,
        level=settings.log_level.upper(),
        colorize=True,
        backtrace=settings.debug,
        diagnose=settings.debug,
    )

    # Optionally add file logging
    if not settings.debug:
        logger.add(
            "logs/ai_service_{time:YYYY-MM-DD}.log",
            rotation="500 MB",
            retention="30 days",
            level="INFO",
            format=log_format,
        )

    # Intercept standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Quiet noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger.info("Logging configured: level=%s", settings.log_level)
