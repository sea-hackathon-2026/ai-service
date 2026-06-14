"""
TTS REST endpoints.

POST /v1/tts/synthesize - submit a speech synthesis job.
GET  /v1/tts/voices - list available voices.
"""

from __future__ import annotations

from fastapi import APIRouter

from services.ai_api.api.deps import ApiKeyDep, TTSServiceDep, TTSUseCaseDep
from services.ai_api.api.schemas.tts import (
    TTSRequest,
    TTSResponse,
    VoiceInfo,
    VoiceListResponse,
)
from services.ai_api.application.dto.tts_request import TTSRequest as TTSRequestDTO

router = APIRouter(prefix="/tts", tags=["Text-to-Speech"])


@router.post(
    "/synthesize",
    response_model=TTSResponse,
    summary="Synthesize speech",
    description="Submit a TTS synthesis job. Returns immediately with the result. "
    "For streaming, use the WebSocket endpoint /v1/ws/tts/stream.",
)
async def synthesize(
    request: TTSRequest,
    use_case: TTSUseCaseDep,
    _api_key: ApiKeyDep,
) -> TTSResponse:
    """Submit a TTS synthesis job (batch mode)."""
    dto = TTSRequestDTO(
        text=request.text,
        voice=request.voice,
        language=request.language,
        audio_format=request.audio_format,
        sample_rate=request.sample_rate,
        speed=request.speed,
    )

    result = await use_case.execute(dto)

    return TTSResponse(
        job_id=result.job_id,
        status="done",
        audio_url=result.url,
        total_chunks=result.total_chunks,
        total_duration_ms=result.total_duration_ms,
        sample_rate=result.sample_rate,
        format=result.format,
    )


@router.get(
    "/voices",
    response_model=VoiceListResponse,
    summary="List available voices",
    description="Returns all available voice options for TTS synthesis.",
)
async def list_voices(
    tts_service: TTSServiceDep,
) -> VoiceListResponse:
    """Get available TTS voices."""
    voices_raw = await tts_service.list_voices()
    voices = [VoiceInfo(**v) for v in voices_raw]
    return VoiceListResponse(voices=voices)
