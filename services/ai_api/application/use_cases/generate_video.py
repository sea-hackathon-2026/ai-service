"""
GenerateVideo use case.

Orchestrates the video generation workflow:
1. Create a Job entity
2. Persist it to the repository
3. Invoke the video service (streaming or batch)
4. Update job progress as chunks arrive
5. Save the final output to storage
6. Mark the job as completed
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from services.ai_api.application.dto.video_request import VideoRequest
from services.ai_api.domain.entities.job import Job
from services.ai_api.domain.entities.video_result import VideoChunk, VideoResult
from services.ai_api.domain.enums.model_type import ModelType
from services.ai_api.domain.exceptions.video import VideoGenerationError, VideoModelNotLoadedError
from services.ai_api.domain.interfaces.job_repository import IJobRepository
from services.ai_api.domain.interfaces.storage_service import IStorageService
from services.ai_api.domain.interfaces.video_service import IVideoService

logger = logging.getLogger(__name__)


class GenerateVideoUseCase:
    """
    Use case for generating videos from text prompts.

    Supports both streaming (WebSocket) and batch (REST) modes.
    """

    def __init__(
        self,
        video_service: IVideoService,
        job_repository: IJobRepository,
        storage_service: IStorageService,
    ) -> None:
        self._video_service = video_service
        self._job_repo = job_repository
        self._storage = storage_service

    async def execute_stream(self, request: VideoRequest) -> AsyncGenerator[VideoChunk, None]:
        """
        Execute video generation with real-time chunk streaming.

        Creates a job, streams chunks to the caller (for WebSocket forwarding),
        and updates job status throughout the process.

        Yields:
            VideoChunk: Individual video data chunks for real-time delivery.
        """
        if not await self._video_service.is_ready():
            raise VideoModelNotLoadedError()

        # Create and persist job
        job = Job(
            model_type=ModelType.VIDEO_GEN,
            input_params={"prompt": request.prompt, **request.model_config},
        )
        job = await self._job_repo.create(job)
        job.start_processing()
        await self._job_repo.update(job)

        logger.info("Starting streaming video generation for job %s", job.id)

        try:
            async for chunk in self._video_service.generate_stream(
                prompt=request.prompt,
                config=request.model_config,
                job_id=job.id,
            ):
                # Update progress
                if chunk.total_frames:
                    progress = (chunk.frame_idx + 1) / chunk.total_frames
                    job.update_progress(progress, f"generating_frame_{chunk.frame_idx}")
                    await self._job_repo.update(job)

                yield chunk

                # If final chunk, mark job complete
                if chunk.is_final:
                    # Save to storage
                    filename = f"videos/{job.id}.mp4"
                    url = await self._storage.save(chunk.data, filename, "video/mp4")
                    job.complete(url)
                    await self._job_repo.update(job)

        except Exception as e:
            logger.error("Video generation failed for job %s: %s", job.id, e)
            job.fail(str(e))
            await self._job_repo.update(job)
            raise VideoGenerationError(str(e)) from e

    async def execute(self, request: VideoRequest) -> VideoResult:
        """
        Execute video generation in batch mode (non-streaming).

        Returns:
            VideoResult: Metadata about the generated video.
        """
        if not await self._video_service.is_ready():
            raise VideoModelNotLoadedError()

        job = Job(
            model_type=ModelType.VIDEO_GEN,
            input_params={"prompt": request.prompt, **request.model_config},
        )
        job = await self._job_repo.create(job)
        job.start_processing()
        await self._job_repo.update(job)

        try:
            result = await self._video_service.generate(
                prompt=request.prompt,
                config=request.model_config,
                job_id=job.id,
            )
            job.complete(result.url)
            await self._job_repo.update(job)
            return result

        except Exception as e:
            job.fail(str(e))
            await self._job_repo.update(job)
            raise VideoGenerationError(str(e)) from e
