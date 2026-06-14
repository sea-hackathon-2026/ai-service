"""
Health check endpoints.

Provides /health and /readiness probes for load balancers,
Kubernetes, and monitoring systems.
"""

from __future__ import annotations

from fastapi import APIRouter

from services.ai_api.api.deps import get_tts_service, get_video_service
from services.ai_api.api.schemas.common import HealthResponse
from services.ai_api.config import get_settings

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Basic liveness probe. Returns 200 if the service is running.",
)
async def health_check() -> HealthResponse:
    """Liveness probe."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
    )


@router.get(
    "/readiness",
    response_model=HealthResponse,
    summary="Readiness check",
    description="Checks if all dependent services (AI models, DB) are ready.",
)
async def readiness_check() -> HealthResponse:
    """Readiness probe — verifies all dependencies are available."""
    settings = get_settings()

    video_ready = await get_video_service().is_ready()
    tts_ready = await get_tts_service().is_ready()

    all_ready = video_ready and tts_ready
    return HealthResponse(
        status="ready" if all_ready else "degraded",
        version=settings.app_version,
        services={
            "video_model": "ready" if video_ready else "not_ready",
            "tts_model": "ready" if tts_ready else "not_ready",
        },
    )
