"""Application orchestration for micro-scene livestream video jobs."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from services.ai_api.application.dto.livestream_video_request import (
    LivestreamVideoRequest,
)
from services.ai_api.application.ports.livestream_pipeline import (
    LivestreamPipeline,
    LivestreamPipelineResult,
)
from services.ai_api.domain.entities.job import Job
from services.ai_api.domain.enums.model_type import ModelType
from services.ai_api.domain.exceptions.base import EntityNotFoundError
from services.ai_api.domain.interfaces.job_unit_of_work import IJobUnitOfWork

logger = logging.getLogger(__name__)
UnitOfWorkFactory = Callable[[], IJobUnitOfWork]
PipelineFactory = Callable[[], LivestreamPipeline]


class GenerateLivestreamVideoUseCase:
    """Persist and execute a video job split into short renderable scenes."""

    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        pipeline_factory: PipelineFactory,
        public_url_prefix: str = "/outputs",
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._pipeline_factory = pipeline_factory
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
        async with self._unit_of_work_factory() as unit_of_work:
            job = await unit_of_work.jobs.create(job)
            job.start_processing()
            await unit_of_work.jobs.update(job)
            await unit_of_work.commit()
        return job

    async def attach_inputs(
        self,
        job_id: str,
        request: LivestreamVideoRequest,
    ) -> Job:
        async with self._unit_of_work_factory() as unit_of_work:
            job = await unit_of_work.jobs.get_by_id(job_id)
            if job is None:
                raise EntityNotFoundError("Job", job_id)
            job.input_params.update(
                {
                    "model_image_path": request.model_image_path,
                    "product_image_path": request.product_image_path,
                    "job_dir": request.job_dir,
                }
            )
            await unit_of_work.jobs.update(job)
            await unit_of_work.commit()
        return job

    async def run_job(self, job_id: str, request: LivestreamVideoRequest) -> None:
        """Run blocking media work in a thread and persist progress safely."""

        loop = asyncio.get_running_loop()

        def progress_callback(status: str, progress: float, current_step: str) -> None:
            future = asyncio.run_coroutine_threadsafe(
                self._update_progress(job_id, progress, status, current_step),
                loop,
            )
            future.result()

        pipeline = self._pipeline_factory()
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
        except Exception as exc:
            logger.exception("Livestream job %s failed", job_id)
            await self._fail_job(job_id, str(exc))

    async def get_outputs(self, job_id: str) -> dict[str, Any]:
        async with self._unit_of_work_factory() as unit_of_work:
            job = await unit_of_work.jobs.get_by_id(job_id)
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
        progress: float,
        stage: str,
        current_step: str,
    ) -> None:
        async with self._unit_of_work_factory() as unit_of_work:
            job = await unit_of_work.jobs.get_by_id(job_id)
            if job is None:
                raise EntityNotFoundError("Job", job_id)
            job.update_progress(progress, stage)
            job.input_params["current_step"] = current_step
            await unit_of_work.jobs.update(job)
            await unit_of_work.commit()

    async def _complete_job(
        self,
        job_id: str,
        result: LivestreamPipelineResult,
    ) -> None:
        async with self._unit_of_work_factory() as unit_of_work:
            job = await unit_of_work.jobs.get_by_id(job_id)
            if job is None:
                raise EntityNotFoundError("Job", job_id)
            job.input_params.update(
                {
                    "current_step": "Done",
                    "scene_plan_path": result.scene_plan_path,
                    "scene_plan_url": self._public_url(job_id, "plan/scene_plan.json"),
                    "scene_outputs": [scene.to_dict() for scene in result.scenes],
                    "final_video_path": result.final_video_path,
                    "duration_sec": result.duration_sec,
                }
            )
            job.complete(result.final_video_url)
            await unit_of_work.jobs.update(job)
            await unit_of_work.commit()

    async def _fail_job(self, job_id: str, error_message: str) -> None:
        async with self._unit_of_work_factory() as unit_of_work:
            job = await unit_of_work.jobs.get_by_id(job_id)
            if job is None:
                logger.error("Could not mark missing job %s as failed", job_id)
                return
            job.input_params["current_step"] = "Generation failed"
            job.fail(error_message)
            await unit_of_work.jobs.update(job)
            await unit_of_work.commit()

    def _public_url(self, job_id: str, relative_path: str) -> str:
        return f"{self._public_url_prefix}/livestream/{job_id}/{relative_path}"
