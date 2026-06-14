"""
IVideoService - Abstract interface for video generation adapters.

Any concrete video generation backend (CogVideoX, AnimateDiff, Wan, etc.)
must implement this interface. The key method `generate_stream` yields
VideoChunk objects for real-time WebSocket delivery.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from services.ai_api.domain.entities.video_result import VideoChunk, VideoResult


class IVideoService(ABC):
    """Port for video generation services."""

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        config: dict[str, Any],
        job_id: str,
    ) -> AsyncGenerator[VideoChunk, None]:
        """
        Generate video frames as an async stream of chunks.

        Args:
            prompt: Text prompt describing the video to generate.
            config: Model-specific configuration (resolution, fps, duration, etc.).
            job_id: Unique identifier for tracking this generation job.

        Yields:
            VideoChunk: Individual frame/segment data for real-time streaming.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        config: dict[str, Any],
        job_id: str,
    ) -> VideoResult:
        """
        Generate a complete video (non-streaming).

        Args:
            prompt: Text prompt describing the video to generate.
            config: Model-specific configuration.
            job_id: Unique identifier for this generation job.

        Returns:
            VideoResult: Metadata about the generated video including URL.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def is_ready(self) -> bool:
        """Check if the video generation model is loaded and ready."""
        ...  # pragma: no cover

    @abstractmethod
    async def get_supported_config(self) -> dict[str, Any]:
        """Return supported configuration options and their defaults."""
        ...  # pragma: no cover
