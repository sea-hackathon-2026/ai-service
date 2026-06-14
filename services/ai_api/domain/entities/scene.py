"""Scene entities for micro-scene video generation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SceneType = Literal[
    "HOST_TALK",
    "HOST_PHONE_READING",
    "PRODUCT_CLOSEUP",
    "PRODUCT_BEAUTY",
    "CTA",
    "TRANSITION",
]


class SceneChunk(BaseModel):
    """A short script chunk with the visual plan needed to render one clip."""

    scene_id: str
    order: int
    scene_type: SceneType
    text: str = Field(..., min_length=1)
    visual_goal: str
    emotion: str
    camera: str
    host_action: str
    product_action: str
    duration_target_sec: float = Field(3.0, gt=0)
    image_prompt: str = ""
    negative_prompt: str
    motion_prompt: str
    overlay_text: str | None = None
    use_lipsync: bool = True
    use_product_overlay: bool = False
