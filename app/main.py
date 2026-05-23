"""
AI Service - FastAPI Application Factory.

Creates and configures the FastAPI application with:
- Lifespan events (startup/shutdown)
- All REST and WebSocket routes
- Middleware stack (CORS, Auth, Rate Limiting)
- Exception handlers
- Static file serving for generated outputs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.middlewares.cors import add_cors_middleware
from app.api.middlewares.rate_limit import RateLimitMiddleware
from app.api.v1.router import api_v1_router, health_router_global, ws_router
from app.config import get_settings
from app.core.logging import setup_logging
from app.domain.exceptions.base import DomainException
from app.infrastructure.persistence.database import close_db, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Startup:
    - Configure logging
    - Initialize database (create tables)
    - Ensure output directories exist
    - (Future) Load AI models into GPU memory

    Shutdown:
    - Close database connections
    - (Future) Unload AI models from GPU memory
    """
    # ── Startup ──
    setup_logging()
    logger.info("🚀 Starting AI Service...")

    # Initialize database
    await init_db()
    logger.info("✅ Database initialized")

    # Ensure output directories exist
    settings = get_settings()
    output_path = Path(settings.storage_local_path)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "videos").mkdir(exist_ok=True)
    (output_path / "audio").mkdir(exist_ok=True)
    (output_path / "livestream").mkdir(exist_ok=True)
    logger.info("✅ Storage directories ready: %s", output_path)

    # Data directory for SQLite
    Path("./data").mkdir(exist_ok=True)

    logger.info("✅ AI Service ready on %s:%s", settings.host, settings.port)

    yield

    # ── Shutdown ──
    logger.info("🛑 Shutting down AI Service...")
    await close_db()
    logger.info("✅ Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AI Service Backend — Video Generation & Text-to-Speech API "
            "with real-time WebSocket streaming for website integration."
        ),
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # ── Middleware Stack (order matters: last added = first executed) ──
    # Rate limiting
    app.add_middleware(RateLimitMiddleware, rate_limit=60, window_sec=60)

    # CORS for website integration
    add_cors_middleware(app)

    # ── Exception Handlers ──
    @app.exception_handler(DomainException)
    async def domain_exception_handler(
        request: Request, exc: DomainException
    ) -> JSONResponse:
        """Translate domain exceptions to HTTP error responses."""
        status_map = {
            "NOT_FOUND": 404,
            "VALIDATION_ERROR": 422,
            "SERVICE_UNAVAILABLE": 503,
            "MODEL_NOT_LOADED": 503,
        }
        status_code = status_map.get(exc.code, 500)
        return JSONResponse(
            status_code=status_code,
            content={"code": exc.code, "message": exc.message},
        )

    # ── Routes ──
    # Health checks (public, no auth required)
    app.include_router(health_router_global)

    # REST API v1
    app.include_router(api_v1_router)

    # WebSocket endpoints
    app.include_router(ws_router)

    # ── Static Files (serve generated outputs) ──
    output_dir = Path(settings.storage_local_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/static/outputs",
        StaticFiles(directory=str(output_dir)),
        name="outputs",
    )

    return app


# Application instance
app = create_app()
