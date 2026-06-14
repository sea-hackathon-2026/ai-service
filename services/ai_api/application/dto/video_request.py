"""
VideoRequest DTO - Internal representation of a video generation request.

Decouples the API schema from the use case layer, allowing the use case
to work with a clean, validated data structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VideoRequest:
    """DTO for video generation use case input."""

    prompt: str
    width: int = 512
    height: int = 512
    num_frames: int = 49
    fps: int = 24
    duration_sec: float = 2.0
    guidance_scale: float = 6.0
    num_inference_steps: int = 50
    seed: int | None = None
    extra_config: dict[str, Any] = field(default_factory=dict)

    @property
    def model_config(self) -> dict[str, Any]:
        """Merge all config into a single dict for the model adapter."""
        return {
            "width": self.width,
            "height": self.height,
            "num_frames": self.num_frames,
            "fps": self.fps,
            "duration_sec": self.duration_sec,
            "guidance_scale": self.guidance_scale,
            "num_inference_steps": self.num_inference_steps,
            "seed": self.seed,
            **self.extra_config,
        }
