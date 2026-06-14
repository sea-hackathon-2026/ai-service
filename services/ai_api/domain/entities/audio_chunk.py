"""
AudioChunk entity - Represents a chunk of audio data from TTS streaming.

Used for real-time audio delivery where the client can start playback
before the entire synthesis is complete.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AudioChunk:
    """A single chunk of audio data emitted during TTS streaming."""

    job_id: str
    chunk_idx: int
    data: bytes  # Raw PCM or encoded audio bytes
    sample_rate: int = 22050
    channels: int = 1
    format: str = "wav"  # "wav" | "mp3" | "opus"
    duration_ms: float = 0.0
    is_final: bool = False


@dataclass
class TTSResult:
    """Domain entity for a completed TTS output."""

    job_id: str
    url: str
    total_chunks: int = 0
    total_duration_ms: float = 0.0
    sample_rate: int = 22050
    format: str = "wav"
    file_size_bytes: int = 0
    text_length: int = 0
