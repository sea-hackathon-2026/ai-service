"""Video API schemas - Request and response models for video generation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VideoGenerateRequest(BaseModel):
    """REST API request for video generation."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Text prompt describing the video to generate",
    )
    width: int = Field(512, ge=128, le=1920, description="Video width in pixels")
    height: int = Field(512, ge=128, le=1080, description="Video height in pixels")
    num_frames: int = Field(49, ge=8, le=120, description="Number of frames to generate")
    fps: int = Field(24, ge=8, le=60, description="Frames per second")
    duration_sec: float = Field(2.0, ge=0.5, le=10.0, description="Target duration in seconds")
    guidance_scale: float = Field(
        6.0, ge=1.0, le=20.0, description="Classifier-free guidance scale"
    )
    num_inference_steps: int = Field(50, ge=10, le=200, description="Denoising steps")
    seed: int | None = Field(None, description="Random seed for reproducibility")


class VideoGenerateResponse(BaseModel):
    """REST API response for completed video generation."""

    job_id: str
    status: str
    video_url: str | None = None
    width: int = 512
    height: int = 512
    duration_sec: float = 0.0
    fps: int = 24
    format: str = "mp4"


class VideoConfigResponse(BaseModel):
    """Supported video generation configuration options."""

    config: dict[str, Any]


class LivestreamJobResponse(BaseModel):
    """Response returned after submitting a micro-scene livestream job."""

    job_id: str
    status: str
    status_url: str
    outputs_url: str


class LivestreamSceneOutput(BaseModel):
    """Metadata for one rendered livestream scene clip."""

    scene_id: str
    order: int
    scene_type: str
    text: str
    visual_goal: str
    emotion: str
    camera: str
    host_action: str
    product_action: str
    duration_target_sec: float
    image_prompt: str = ""
    negative_prompt: str
    motion_prompt: str
    overlay_text: str | None = None
    use_lipsync: bool = True
    use_product_overlay: bool = False
    video_path: str | None = None
    url: str | None = None


class LivestreamOutputsResponse(BaseModel):
    """Generated scene clips and final video for a livestream job."""

    job_id: str
    status: str
    progress: float
    current_step: str
    videos: list[LivestreamSceneOutput] = Field(default_factory=list)
    scene_plan_url: str | None = None
    final_video_url: str | None = None
    error_message: str | None = None
