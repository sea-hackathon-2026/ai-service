"""Route composition for the public AI API."""

from fastapi import APIRouter

from services.ai_api.api.v1.endpoints import health
from services.ai_api.api.v1.endpoints.jobs import router as jobs_router
from services.ai_api.api.v1.endpoints.tts import router as tts_router
from services.ai_api.api.v1.endpoints.video import router as video_router
from services.ai_api.api.v1.endpoints.websockets.tts_ws import (
    router as tts_ws_router,
)
from services.ai_api.api.v1.endpoints.websockets.video_ws import (
    router as video_ws_router,
)

health_router = health.router
api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(video_router)
api_v1_router.include_router(tts_router)
api_v1_router.include_router(jobs_router)

ws_router = APIRouter(prefix="/v1")
ws_router.include_router(video_ws_router)
ws_router.include_router(tts_ws_router)
