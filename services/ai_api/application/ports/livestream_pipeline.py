"""Provider-independent contract for livestream media rendering."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from services.ai_api.domain.entities.scene import SceneChunk

ProgressCallback = Callable[[str, float, str], None]


@dataclass(frozen=True)
class GeneratedScene:
    """Metadata for one rendered scene clip."""

    scene: SceneChunk
    video_path: str
    public_url: str

    def to_dict(self) -> dict[str, str | int | float | bool | None]:
        data = self.scene.model_dump()
        data["video_path"] = self.video_path
        data["url"] = self.public_url
        return data


@dataclass(frozen=True)
class LivestreamPipelineResult:
    """Provider-independent result of a completed render pipeline."""

    final_video_path: str
    final_video_url: str
    scene_plan_path: str
    scenes: list[GeneratedScene]
    duration_sec: float


class LivestreamPipeline(Protocol):
    """Render a complete livestream asset from text and reference images."""

    def generate(
        self,
        *,
        job_id: str,
        product_name: str,
        product_description: str,
        brand_style: str,
        script: str,
        model_image_path: str,
        product_image_path: str,
        job_dir: str,
        voice: str,
        progress_callback: ProgressCallback | None = None,
    ) -> LivestreamPipelineResult: ...
