"""
GetJobStatus use case.

Simple query use case to retrieve job status and progress,
used by both REST polling and WebSocket status checks.
"""

from __future__ import annotations

from services.ai_api.domain.entities.job import Job
from services.ai_api.domain.exceptions.base import EntityNotFoundError
from services.ai_api.domain.interfaces.job_repository import IJobRepository


class GetJobStatusUseCase:
    """Use case for querying job status and progress."""

    def __init__(self, job_repository: IJobRepository) -> None:
        self._job_repo = job_repository

    async def execute(self, job_id: str) -> Job:
        """
        Retrieve a job by ID.

        Args:
            job_id: Unique identifier of the job.

        Returns:
            Job entity with current status and progress.

        Raises:
            EntityNotFoundError: If the job does not exist.
        """
        job = await self._job_repo.get_by_id(job_id)
        if job is None:
            raise EntityNotFoundError("Job", job_id)
        return job
