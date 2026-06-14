"""
WebSocket message protocol schemas.

Defines the JSON message format for WebSocket communication between
API clients and the AI service backend.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Client → Server Messages ──


class WSAuthMessage(BaseModel):
    """Authentication message from client."""

    type: str = "authenticate"
    api_key: str


class WSVideoGenerateMessage(BaseModel):
    """Video generation request via WebSocket."""

    type: str = "generate"
    prompt: str = Field(..., min_length=1, max_length=2000)
    config: dict[str, Any] = Field(default_factory=dict)


class WSTTSSynthesizeMessage(BaseModel):
    """TTS synthesis request via WebSocket."""

    type: str = "synthesize"
    text: str = Field(..., min_length=1, max_length=10000)
    voice: str = "default"
    language: str = "vi"
    format: str = "wav"


class WSCancelMessage(BaseModel):
    """Cancel a running job."""

    type: str = "cancel"
    job_id: str


# ── Server → Client Messages ──


class WSAuthenticatedMessage(BaseModel):
    """Sent after successful authentication."""

    type: str = "authenticated"
    session_id: str


class WSProgressMessage(BaseModel):
    """Progress update during generation."""

    type: str = "progress"
    job_id: str
    percent: float = Field(ge=0, le=100)
    stage: str


class WSVideoChunkMessage(BaseModel):
    """A video frame chunk delivered via WebSocket."""

    type: str = "frame_chunk"
    job_id: str
    data: str  # base64-encoded frame data
    chunk_idx: int
    frame_idx: int
    total_frames: int | None = None


class WSAudioChunkMessage(BaseModel):
    """An audio chunk delivered via WebSocket."""

    type: str = "audio_chunk"
    job_id: str
    data: str  # base64-encoded audio data
    chunk_idx: int
    sample_rate: int = 22050
    duration_ms: float = 0.0


class WSCompleteMessage(BaseModel):
    """Sent when generation is fully complete."""

    type: str = "complete"
    job_id: str
    url: str | None = None
    total_chunks: int = 0
    duration_ms: float = 0.0


class WSErrorMessage(BaseModel):
    """Error message from server."""

    type: str = "error"
    code: str
    message: str
    job_id: str | None = None


class WSPingMessage(BaseModel):
    """Heartbeat ping/pong."""

    type: str = "ping"
    timestamp: float
