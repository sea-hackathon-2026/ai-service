"""
VideoResult entity - Represents the output of a video generation process.

Contains metadata about the generated video including resolution,
duration, and the storage URL for retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class VideoResult:
    """Domain entity for a generated video output."""

    job_id: str
    url: str
    width: int = 512
    height: int = 512
    duration_sec: float = 0.0
    fps: int = 24
    format: str = "mp4"
    file_size_bytes: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class VideoChunk:
    """
    A single chunk of video data emitted during streaming generation.

    Used by WebSocket to push partial results to the client in real-time.
    """

    job_id: str
    chunk_idx: int
    data: bytes  # Raw frame data or encoded segment
    frame_idx: int = 0
    total_frames: int | None = None
    is_final: bool = False
    metadata: dict = field(default_factory=dict)
