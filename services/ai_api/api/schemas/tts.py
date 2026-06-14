"""TTS API schemas - Request and response models for text-to-speech."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """REST API request for text-to-speech synthesis."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Text to synthesize into speech",
    )
    voice: str = Field("default", description="Voice identifier")
    language: str = Field("vi", description="Language code (e.g., 'vi', 'en')")
    audio_format: str = Field("wav", description="Output format: wav, mp3, opus")
    sample_rate: int = Field(22050, ge=8000, le=48000, description="Sample rate in Hz")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speech speed multiplier")


class TTSResponse(BaseModel):
    """REST API response for completed TTS synthesis."""

    job_id: str
    status: str
    audio_url: str | None = None
    total_chunks: int = 0
    total_duration_ms: float = 0.0
    sample_rate: int = 22050
    format: str = "wav"


class VoiceInfo(BaseModel):
    """Information about an available voice."""

    id: str
    name: str
    language: str


class VoiceListResponse(BaseModel):
    """List of available voices."""

    voices: list[VoiceInfo]
