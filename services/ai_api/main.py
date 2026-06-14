"""FastAPI application factory for AI media orchestration."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from services.ai_api.api.middlewares.cors import add_cors_middleware
from services.ai_api.api.middlewares.rate_limit import RateLimitMiddleware
from services.ai_api.api.v1.router import api_v1_router, health_router, ws_router
from services.ai_api.config import get_settings
from services.ai_api.core.logging import setup_logging
from services.ai_api.domain.exceptions.base import DomainException
from services.ai_api.infrastructure.persistence.database import close_db, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_application: FastAPI):
    """Initialize persistence and writable storage for one process."""

    setup_logging()
    settings = get_settings()
    await init_db()
    for directory in ("videos", "audio", "livestream"):
        (settings.storage_path / directory).mkdir(parents=True, exist_ok=True)
    Path("./data").mkdir(exist_ok=True)
    logger.info("AI API started on %s:%s", settings.host, settings.port)
    yield
    await close_db()
    logger.info("AI API stopped")


def create_app() -> FastAPI:
    """Compose adapters, middleware, exception mapping, and HTTP routes."""

    settings = get_settings()
    application = FastAPI(
        title="AI Media Orchestration API",
        version=settings.app_version,
        description=(
            "Job-oriented video and speech generation with REST and WebSocket "
            "transports. Model implementations are injected adapters."
        ),
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )
    application.add_middleware(RateLimitMiddleware, rate_limit=60, window_sec=60)
    add_cors_middleware(application)

    @application.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
        status_code = {
            "NOT_FOUND": 404,
            "VALIDATION_ERROR": 422,
            "SERVICE_UNAVAILABLE": 503,
            "MODEL_NOT_LOADED": 503,
        }.get(exc.code, 500)
        return JSONResponse(
            status_code=status_code,
            content={"code": exc.code, "message": exc.message},
        )

    application.include_router(health_router)
    application.include_router(api_v1_router)
    application.include_router(ws_router)
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    application.mount(
        "/outputs",
        StaticFiles(directory=str(settings.storage_path)),
        name="outputs",
    )
    return application


app = create_app()
