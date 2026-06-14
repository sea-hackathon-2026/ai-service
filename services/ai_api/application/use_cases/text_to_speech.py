"""
TextToSpeech use case.

Orchestrates the TTS workflow:
1. Create a Job entity
2. Invoke the TTS service with streaming
3. Yield audio chunks for real-time WebSocket delivery
4. Save the assembled audio to storage
5. Mark the job as completed
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from services.ai_api.application.dto.tts_request import TTSRequest
from services.ai_api.domain.entities.audio_chunk import AudioChunk, TTSResult
from services.ai_api.domain.entities.job import Job
from services.ai_api.domain.enums.model_type import ModelType
from services.ai_api.domain.exceptions.base import ServiceUnavailableError
from services.ai_api.domain.exceptions.tts import TTSError
from services.ai_api.domain.interfaces.job_repository import IJobRepository
from services.ai_api.domain.interfaces.storage_service import IStorageService
from services.ai_api.domain.interfaces.tts_service import ITTSService

logger = logging.getLogger(__name__)


class TextToSpeechUseCase:
    """
    Use case for synthesizing speech from text.

    Supports both streaming (WebSocket) and batch (REST) modes.
    """

    def __init__(
        self,
        tts_service: ITTSService,
        job_repository: IJobRepository,
        storage_service: IStorageService,
    ) -> None:
        self._tts_service = tts_service
        self._job_repo = job_repository
        self._storage = storage_service

    async def execute_stream(self, request: TTSRequest) -> AsyncGenerator[AudioChunk, None]:
        """
        Execute TTS with real-time audio chunk streaming.

        Yields:
            AudioChunk: Individual audio segments for immediate playback.
        """
        if not await self._tts_service.is_ready():
            raise ServiceUnavailableError("tts")

        job = Job(
            model_type=ModelType.TTS,
            input_params={
                "text": request.text,
                "voice": request.voice,
                "language": request.language,
                "format": request.audio_format,
            },
        )
        job = await self._job_repo.create(job)
        job.start_processing()
        await self._job_repo.update(job)

        logger.info("Starting streaming TTS for job %s", job.id)

        total_chunks = 0
        total_duration_ms = 0.0

        try:
            async for chunk in self._tts_service.synthesize_stream(
                text=request.text,
                voice=request.voice,
                audio_format=request.audio_format,
                job_id=job.id,
                config=request.extra_config or None,
            ):
                total_chunks += 1
                total_duration_ms += chunk.duration_ms

                # Update progress (estimate based on text length processed)
                job.update_progress(
                    min(total_chunks * 0.1, 0.95),
                    f"synthesizing_chunk_{chunk.chunk_idx}",
                )
                await self._job_repo.update(job)

                yield chunk

                if chunk.is_final:
                    # Save assembled audio
                    filename = f"audio/{job.id}.{request.audio_format}"
                    url = await self._storage.save(
                        chunk.data, filename, f"audio/{request.audio_format}"
                    )
                    job.complete(url)
                    await self._job_repo.update(job)

        except Exception as e:
            logger.error("TTS failed for job %s: %s", job.id, e)
            job.fail(str(e))
            await self._job_repo.update(job)
            raise TTSError(str(e)) from e

    async def execute(self, request: TTSRequest) -> TTSResult:
        """Execute TTS in batch mode (non-streaming)."""
        if not await self._tts_service.is_ready():
            raise ServiceUnavailableError("tts")

        job = Job(
            model_type=ModelType.TTS,
            input_params={"text": request.text, "voice": request.voice},
        )
        job = await self._job_repo.create(job)
        job.start_processing()
        await self._job_repo.update(job)

        try:
            result = await self._tts_service.synthesize(
                text=request.text,
                voice=request.voice,
                audio_format=request.audio_format,
                job_id=job.id,
            )
            job.complete(result.url)
            await self._job_repo.update(job)
            return result

        except Exception as e:
            job.fail(str(e))
            await self._job_repo.update(job)
            raise TTSError(str(e)) from e
