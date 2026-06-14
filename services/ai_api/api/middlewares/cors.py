"""
CORS middleware configuration.

Configures Cross-Origin Resource Sharing to allow website integration.
Origins are loaded from CORS_ORIGINS config.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.ai_api.config import get_settings


def add_cors_middleware(app: FastAPI) -> None:
    """Add CORS middleware with configured origins."""
    settings = get_settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
