"""
ITTSService - Abstract interface for Text-to-Speech adapters.

Any concrete TTS backend (Bark, XTTS, VITS, Edge-TTS, etc.)
must implement this interface. The key method `synthesize_stream` yields
AudioChunk objects for real-time WebSocket delivery.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from services.ai_api.domain.entities.audio_chunk import AudioChunk, TTSResult


class ITTSService(ABC):
    """Port for text-to-speech services."""

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        voice: str,
        audio_format: str,
        job_id: str,
        config: dict[str, Any] | None = None,
    ) -> AsyncGenerator[AudioChunk, None]:
        """
        Synthesize speech as an async stream of audio chunks.

        Args:
            text: Input text to synthesize.
            voice: Voice identifier (e.g., "vi-female-01").
            audio_format: Output format ("wav", "mp3", "opus").
            job_id: Unique identifier for tracking this synthesis job.
            config: Optional model-specific configuration.

        Yields:
            AudioChunk: Individual audio segment for real-time streaming.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str,
        audio_format: str,
        job_id: str,
    ) -> TTSResult:
        """
        Synthesize complete audio (non-streaming).

        Returns:
            TTSResult: Metadata about the synthesized audio including URL.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def is_ready(self) -> bool:
        """Check if the TTS model is loaded and ready."""
        ...  # pragma: no cover

    @abstractmethod
    async def list_voices(self) -> list[dict[str, str]]:
        """Return available voice options with metadata."""
        ...  # pragma: no cover
