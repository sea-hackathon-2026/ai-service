"""
API v1 Router - Aggregates all v1 REST and WebSocket routes.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.video import router as video_router
from app.api.v1.endpoints.tts import router as tts_router
from app.api.v1.endpoints.jobs import router as jobs_router
from app.api.v1.endpoints.websockets.video_ws import router as video_ws_router
from app.api.v1.endpoints.websockets.tts_ws import router as tts_ws_router

# REST API v1 router
api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(video_router)
api_v1_router.include_router(tts_router)
api_v1_router.include_router(jobs_router)

# Health routes (no prefix — accessible at /health, /readiness)
health_router_global = health_router

# WebSocket routes (no API version prefix for simpler client URLs)
ws_router = APIRouter()
ws_router.include_router(video_ws_router)
ws_router.include_router(tts_ws_router)
