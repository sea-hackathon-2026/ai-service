"""
TTSRequest DTO - Internal representation of a text-to-speech request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TTSRequest:
    """DTO for TTS use case input."""

    text: str
    voice: str = "default"
    language: str = "vi"
    audio_format: str = "wav"  # "wav" | "mp3" | "opus"
    sample_rate: int = 22050
    speed: float = 1.0
    extra_config: dict[str, Any] = field(default_factory=dict)
