"""
Mock TTS Engine adapter.

A development/testing implementation of ITTSService that generates
fake audio chunks with simulated delays. Replace with your actual
TTS model adapter (XTTS, Bark, VITS, Edge-TTS, etc.) for production.

To create a real adapter:
1. Copy this file as a starting point
2. Replace `_generate_fake_audio` with actual TTS inference
3. The `synthesize_stream` method should yield AudioChunk objects
   as the model produces audio segments, enabling real-time playback
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from services.ai_api.domain.entities.audio_chunk import AudioChunk, TTSResult
from services.ai_api.domain.interfaces.tts_service import ITTSService

logger = logging.getLogger(__name__)

# Characters per chunk for simulated chunking
_CHARS_PER_CHUNK = 50


class MockTTSEngine(ITTSService):
    """
    Mock TTS service for development and testing.

    Simulates a TTS pipeline that produces audio chunks from text,
    with artificial delays to demonstrate the streaming protocol.
    """

    AVAILABLE_VOICES = [
        {"id": "vi-female-01", "name": "Vietnamese Female 1", "language": "vi"},
        {"id": "vi-male-01", "name": "Vietnamese Male 1", "language": "vi"},
        {"id": "en-female-01", "name": "English Female 1", "language": "en"},
        {"id": "en-male-01", "name": "English Male 1", "language": "en"},
    ]

    def __init__(self) -> None:
        self._ready = True

    async def synthesize_stream(
        self,
        text: str,
        voice: str,
        audio_format: str,
        job_id: str,
        config: dict[str, Any] | None = None,
    ) -> AsyncGenerator[AudioChunk, None]:
        """
        Simulate streaming TTS with mock audio chunks.

        Splits text into segments and yields fake audio data for each.
        """
        # Split text into chunks for streaming
        text_chunks = [
            text[i : i + _CHARS_PER_CHUNK] for i in range(0, len(text), _CHARS_PER_CHUNK)
        ]
        total_chunks = len(text_chunks)

        logger.info(
            "Mock TTS: job=%s, voice=%s, text_len=%d, chunks=%d",
            job_id,
            voice,
            len(text),
            total_chunks,
        )

        for idx, text_segment in enumerate(text_chunks):
            # Simulate synthesis delay (proportional to text length)
            await asyncio.sleep(0.1 * len(text_segment) / _CHARS_PER_CHUNK)

            is_final = idx == total_chunks - 1
            fake_audio = self._generate_fake_audio(text_segment, 22050)

            yield AudioChunk(
                job_id=job_id,
                chunk_idx=idx,
                data=fake_audio,
                sample_rate=22050,
                channels=1,
                format=audio_format,
                duration_ms=len(text_segment) * 60.0,  # ~60ms per char (rough estimate)
                is_final=is_final,
            )

        logger.info("Mock TTS completed for job %s", job_id)

    async def synthesize(
        self,
        text: str,
        voice: str,
        audio_format: str,
        job_id: str,
    ) -> TTSResult:
        """Generate complete mock audio (non-streaming)."""
        await asyncio.sleep(len(text) * 0.01)  # Simulate processing

        return TTSResult(
            job_id=job_id,
            url=f"/outputs/audio/{job_id}.{audio_format}",
            total_chunks=max(1, len(text) // _CHARS_PER_CHUNK),
            total_duration_ms=len(text) * 60.0,
            sample_rate=22050,
            format=audio_format,
            text_length=len(text),
        )

    async def is_ready(self) -> bool:
        """Mock is always ready."""
        return self._ready

    async def list_voices(self) -> list[dict[str, str]]:
        """Return available mock voices."""
        return self.AVAILABLE_VOICES

    @staticmethod
    def _generate_fake_audio(text: str, sample_rate: int) -> bytes:
        """
        Generate minimal fake PCM audio data for testing.

        In production, this would be replaced by actual model output.
        """
        # Generate silence as 16-bit PCM (2 bytes per sample)
        num_samples = int(sample_rate * len(text) * 0.06)  # ~60ms per char
        return b"\x00\x00" * num_samples
