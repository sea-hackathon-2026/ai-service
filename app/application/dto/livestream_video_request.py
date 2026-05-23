"""DTOs for livestream micro-scene video generation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LivestreamVideoRequest:
    """Internal request for the micro-scene livestream pipeline."""

    product_name: str
    product_description: str
    script: str
    brand_style: str
    model_image_path: str
    product_image_path: str
    job_dir: str
    voice: str = "vi-VN-HoaiMyNeural"
