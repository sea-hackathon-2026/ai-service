"""
Video generation REST endpoints.

POST /v1/video/generate - submit a video generation job.
GET  /v1/video/config - inspect supported configuration.
"""

from __future__ import annotations

from pathlib import Path

import aiofiles
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from services.ai_api.api.deps import (
    ApiKeyDep,
    LivestreamVideoUseCaseDep,
    SettingsDep,
    VideoServiceDep,
    VideoUseCaseDep,
)
from services.ai_api.api.schemas.video import (
    LivestreamJobResponse,
    LivestreamOutputsResponse,
    VideoConfigResponse,
    VideoGenerateRequest,
    VideoGenerateResponse,
)
from services.ai_api.application.dto.livestream_video_request import LivestreamVideoRequest
from services.ai_api.application.dto.video_request import VideoRequest as VideoRequestDTO
from services.ai_api.domain.exceptions.base import EntityNotFoundError

router = APIRouter(prefix="/video", tags=["Video Generation"])


@router.post(
    "/generate",
    response_model=VideoGenerateResponse,
    summary="Generate a video",
    description="Submit a video generation job. Returns immediately with job_id for polling. "
    "For streaming, use the WebSocket endpoint /v1/ws/video/generate.",
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


@router.post(
    "/livestream/jobs",
    response_model=LivestreamJobResponse,
    summary="Create a micro-scene livestream video job",
    description=(
        "Upload host/product images and a seller script. The service splits the "
        "script into short scenes, generates scene audio/video, then concatenates "
        "the final livestream video in the background."
    ),
)
async def create_livestream_video_job(
    background_tasks: BackgroundTasks,
    use_case: LivestreamVideoUseCaseDep,
    settings: SettingsDep,
    _api_key: ApiKeyDep,
    product_name: str = Form(...),
    script: str = Form(...),
    product_description: str = Form(""),
    brand_style: str = Form("clean ecommerce livestream"),
    voice: str | None = Form(None),
    model_image: UploadFile = File(...),
    product_image: UploadFile = File(...),
) -> LivestreamJobResponse:
    """Submit an async livestream generation job."""

    selected_voice = voice or settings.livestream_tts_voice
    job = await use_case.create_job(
        product_name=product_name,
        product_description=product_description,
        script=script,
        brand_style=brand_style,
        voice=selected_voice,
    )

    job_dir = settings.storage_path / "livestream" / job.id
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    model_path = input_dir / f"model{_safe_image_suffix(model_image.filename)}"
    product_path = input_dir / f"product{_safe_image_suffix(product_image.filename)}"

    await _save_upload(model_image, model_path)
    await _save_upload(product_image, product_path)
    (input_dir / "script.txt").write_text(script, encoding="utf-8")

    request = LivestreamVideoRequest(
        product_name=product_name,
        product_description=product_description,
        script=script,
        brand_style=brand_style,
        model_image_path=str(model_path),
        product_image_path=str(product_path),
        job_dir=str(job_dir),
        voice=selected_voice,
    )
    await use_case.attach_inputs(job.id, request)

    background_tasks.add_task(use_case.run_job, job.id, request)

    return LivestreamJobResponse(
        job_id=job.id,
        status=job.status.value,
        status_url=f"/v1/jobs/{job.id}",
        outputs_url=f"/v1/video/livestream/jobs/{job.id}/outputs",
    )


@router.get(
    "/livestream/jobs/{job_id}/outputs",
    response_model=LivestreamOutputsResponse,
    summary="Get livestream job outputs",
    description="Return generated scene clips and final video URL for a livestream job.",
)
async def get_livestream_video_outputs(
    job_id: str,
    use_case: LivestreamVideoUseCaseDep,
    _api_key: ApiKeyDep,
) -> LivestreamOutputsResponse:
    """Get scene clips and final video URL for a livestream job."""

    try:
        outputs = await use_case.get_outputs(job_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found") from exc

    return LivestreamOutputsResponse(**outputs)


async def _save_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(destination, "wb") as f:
        while chunk := await upload.read(1024 * 1024):
            await f.write(chunk)


def _safe_image_suffix(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return suffix
    return ".png"
