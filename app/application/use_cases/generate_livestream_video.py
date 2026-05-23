"""Use case for the micro-scene livestream video pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.application.dto.livestream_video_request import LivestreamVideoRequest
from app.domain.entities.job import Job
from app.domain.enums.model_type import ModelType
from app.domain.exceptions.base import EntityNotFoundError
from app.domain.interfaces.job_repository import IJobRepository
from app.infrastructure.ai_models.micro_scene_pipeline import (
    MicroScenePipelineConfig,
    MicroScenePipelineResult,
    MicroSceneVideoPipeline,
)
from app.infrastructure.persistence.database import async_session_factory
from app.infrastructure.persistence.repositories.job_repository import (
    SQLAlchemyJobRepository,
)

logger = logging.getLogger(__name__)


class GenerateLivestreamVideoUseCase:
    """Submit and run a video job split into short renderable scenes."""

    def __init__(
        self,
        job_repository: IJobRepository,
        pipeline_config: MicroScenePipelineConfig,
        public_url_prefix: str = "/static/outputs",
    ) -> None:
        self._job_repo = job_repository
        self._pipeline_config = pipeline_config
        self._public_url_prefix = public_url_prefix

    async def create_job(
        self,
        *,
        product_name: str,
        product_description: str,
        script: str,
        brand_style: str,
        voice: str,
    ) -> Job:
        """Create and persist the job before uploaded files are saved."""

        job = Job(
            model_type=ModelType.LIVESTREAM_VIDEO,
            input_params={
                "mode": "livestream_micro_scene",
                "product_name": product_name,
                "product_description": product_description,
                "script": script,
                "brand_style": brand_style,
                "voice": voice,
            },
        )
        job = await self._job_repo.create(job)
        job.start_processing()
        await self._job_repo.update(job)
        return job

    async def attach_inputs(
        self,
        job_id: str,
        request: LivestreamVideoRequest,
    ) -> Job:
        """Attach file paths and job directory after uploads have been persisted."""

        job = await self._job_repo.get_by_id(job_id)
        if job is None:
            raise EntityNotFoundError("Job", job_id)

        job.input_params.update(
            {
                "model_image_path": request.model_image_path,
                "product_image_path": request.product_image_path,
                "job_dir": request.job_dir,
            }
        )
        await self._job_repo.update(job)
        return job

    async def run_job(self, job_id: str, request: LivestreamVideoRequest) -> None:
        """Run the blocking media pipeline in a worker thread and update the job."""

        logger.info("Starting livestream micro-scene job %s", job_id)
        loop = asyncio.get_running_loop()

        def progress_callback(status: str, progress: float, current_step: str) -> None:
            future = asyncio.run_coroutine_threadsafe(
                self._update_progress(
                    job_id,
                    progress=progress,
                    stage=status,
                    current_step=current_step,
                ),
                loop,
            )
            future.result()

        pipeline = MicroSceneVideoPipeline(
            config=self._pipeline_config,
            public_url_prefix=self._public_url_prefix,
        )

        try:
            result = await asyncio.to_thread(
                pipeline.generate,
                job_id=job_id,
                product_name=request.product_name,
                product_description=request.product_description,
                brand_style=request.brand_style,
                script=request.script,
                model_image_path=request.model_image_path,
                product_image_path=request.product_image_path,
                job_dir=request.job_dir,
                voice=request.voice,
                progress_callback=progress_callback,
            )
            await self._complete_job(job_id, result)
            logger.info("Livestream micro-scene job %s completed", job_id)
        except Exception as exc:
            logger.exception("Livestream micro-scene job %s failed", job_id)
            await self._fail_job(job_id, str(exc))

    async def get_outputs(self, job_id: str) -> dict[str, Any]:
        """Return generated scene and final-video outputs for a job."""

        job = await self._job_repo.get_by_id(job_id)
        if job is None:
            raise EntityNotFoundError("Job", job_id)

        return {
            "job_id": job.id,
            "status": job.status.value,
            "progress": job.progress,
            "current_step": job.stage,
            "videos": job.input_params.get("scene_outputs", []),
            "scene_plan_url": job.input_params.get("scene_plan_url"),
            "final_video_url": job.result_url,
            "error_message": job.error_message,
        }

    async def _update_progress(
        self,
        job_id: str,
        *,
        progress: float,
        stage: str,
        current_step: str,
    ) -> None:
        async with async_session_factory() as session:
            repo = SQLAlchemyJobRepository(session)
            job = await repo.get_by_id(job_id)
            if job is None:
                raise EntityNotFoundError("Job", job_id)

            job.update_progress(progress, stage)
            job.input_params["current_step"] = current_step
            await repo.update(job)
            await session.commit()

    async def _complete_job(
        self,
        job_id: str,
        result: MicroScenePipelineResult,
    ) -> None:
        async with async_session_factory() as session:
            repo = SQLAlchemyJobRepository(session)
            job = await repo.get_by_id(job_id)
            if job is None:
                raise EntityNotFoundError("Job", job_id)

            job.input_params.update(
                {
                    "current_step": "Done",
                    "scene_plan_path": result.scene_plan_path,
                    "scene_plan_url": self._path_to_public_url(
                        job_id, "plan/scene_plan.json"
                    ),
                    "scene_outputs": [scene.to_dict() for scene in result.scenes],
                    "final_video_path": result.final_video_path,
                    "duration_sec": result.duration_sec,
                }
            )
            job.complete(result.final_video_url)
            await repo.update(job)
            await session.commit()

    async def _fail_job(self, job_id: str, error_message: str) -> None:
        async with async_session_factory() as session:
            repo = SQLAlchemyJobRepository(session)
            job = await repo.get_by_id(job_id)
            if job is None:
                logger.error("Could not mark missing job %s as failed", job_id)
                return

            job.input_params["current_step"] = "Generation failed"
            job.fail(error_message)
            await repo.update(job)
            await session.commit()

    def _path_to_public_url(self, job_id: str, relative_path: str) -> str:
        return f"{self._public_url_prefix}/livestream/{job_id}/{relative_path}"
