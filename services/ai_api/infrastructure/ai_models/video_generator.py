"""
Mock Video Generator adapter.

A development/testing implementation of IVideoService that generates
fake video chunks with simulated delays. Replace with your actual
model adapter (CogVideoX, Wan, AnimateDiff, etc.) for production.

To create a real adapter:
1. Copy this file as a starting point
2. Replace `_generate_fake_chunk` with actual model inference
3. The `generate_stream` method should yield VideoChunk objects
   as the model produces frames, enabling real-time WebSocket delivery
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from services.ai_api.domain.entities.video_result import VideoChunk, VideoResult
from services.ai_api.domain.interfaces.video_service import IVideoService

logger = logging.getLogger(__name__)


class MockVideoGenerator(IVideoService):
    """
    Mock video generation service for development and testing.

    Simulates a video generation pipeline with artificial delays
    to demonstrate the streaming WebSocket protocol.
    """

    def __init__(self) -> None:
        self._ready = True

    async def generate_stream(
        self,
        prompt: str,
        config: dict[str, Any],
        job_id: str,
    ) -> AsyncGenerator[VideoChunk, None]:
        """
        Simulate streaming video generation with mock data.

        Yields fake frame chunks with delays to simulate processing time.
        """
        total_frames = config.get("num_frames", 16)
        logger.info(
            "Mock video gen: job=%s, prompt='%s', frames=%d",
            job_id,
            prompt[:50],
            total_frames,
        )

        for i in range(total_frames):
            # Simulate inference delay per frame
            await asyncio.sleep(0.3)

            # Generate fake frame data (1x1 pixel PNG as placeholder)
            fake_frame = self._generate_fake_frame(i, prompt)

            is_final = i == total_frames - 1

            yield VideoChunk(
                job_id=job_id,
                chunk_idx=i,
                data=fake_frame,
                frame_idx=i,
                total_frames=total_frames,
                is_final=is_final,
                metadata={"stage": "generating", "prompt_hash": hash(prompt)},
            )

        logger.info("Mock video gen completed for job %s", job_id)

    async def generate(
        self,
        prompt: str,
        config: dict[str, Any],
        job_id: str,
    ) -> VideoResult:
        """Generate a complete mock video (non-streaming)."""
        # Simulate full generation time
        total_frames = config.get("num_frames", 16)
        await asyncio.sleep(total_frames * 0.1)

        return VideoResult(
            job_id=job_id,
            url=f"/outputs/videos/{job_id}.mp4",
            width=config.get("width", 512),
            height=config.get("height", 512),
            duration_sec=config.get("duration_sec", 2.0),
            fps=config.get("fps", 24),
        )

    async def is_ready(self) -> bool:
        """Mock is always ready."""
        return self._ready

    async def get_supported_config(self) -> dict[str, Any]:
        """Return mock supported configuration."""
        return {
            "width": {"default": 512, "options": [256, 512, 768, 1024]},
            "height": {"default": 512, "options": [256, 512, 768, 1024]},
            "num_frames": {"default": 49, "min": 8, "max": 120},
            "fps": {"default": 24, "options": [12, 24, 30]},
            "duration_sec": {"default": 2.0, "min": 0.5, "max": 10.0},
            "guidance_scale": {"default": 6.0, "min": 1.0, "max": 20.0},
        }

    @staticmethod
    def _generate_fake_frame(frame_idx: int, prompt: str) -> bytes:
        """Generate a tiny placeholder frame for testing."""
        # Minimal valid data to simulate a frame
        return f"MOCK_FRAME_{frame_idx}_{hash(prompt) % 10000}".encode()
