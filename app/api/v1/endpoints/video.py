"""
Video generation REST endpoints.

POST /api/v1/video/generate — Submit a video generation job
GET  /api/v1/video/config   — Get supported configuration options
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ApiKeyDep, VideoUseCaseDep, VideoServiceDep
from app.api.schemas.video import (
    VideoConfigResponse,
    VideoGenerateRequest,
    VideoGenerateResponse,
)
from app.application.dto.video_request import VideoRequest as VideoRequestDTO

router = APIRouter(prefix="/video", tags=["Video Generation"])


@router.post(
    "/generate",
    response_model=VideoGenerateResponse,
    summary="Generate a video",
    description="Submit a video generation job. Returns immediately with job_id for polling. "
    "For real-time streaming, use the WebSocket endpoint /ws/video/generate instead.",
)
async def generate_video(
    request: VideoGenerateRequest,
    use_case: VideoUseCaseDep,
    _api_key: ApiKeyDep,
) -> VideoGenerateResponse:
    """Submit a video generation job (batch mode)."""
    dto = VideoRequestDTO(
        prompt=request.prompt,
        width=request.width,
        height=request.height,
        num_frames=request.num_frames,
        fps=request.fps,
        duration_sec=request.duration_sec,
        guidance_scale=request.guidance_scale,
        num_inference_steps=request.num_inference_steps,
        seed=request.seed,
    )

    result = await use_case.execute(dto)

    return VideoGenerateResponse(
        job_id=result.job_id,
        status="done",
        video_url=result.url,
        width=result.width,
        height=result.height,
        duration_sec=result.duration_sec,
        fps=result.fps,
        format=result.format,
    )


@router.get(
    "/config",
    response_model=VideoConfigResponse,
    summary="Get video generation config",
    description="Returns supported configuration options and their defaults.",
)
async def get_video_config(
    video_service: VideoServiceDep,
) -> VideoConfigResponse:
    """Get supported video generation configuration."""
    config = await video_service.get_supported_config()
    return VideoConfigResponse(config=config)
