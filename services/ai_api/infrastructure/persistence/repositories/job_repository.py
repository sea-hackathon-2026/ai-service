"""
SQLAlchemy-based Job Repository.

Concrete implementation of IJobRepository using async SQLAlchemy sessions.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_api.domain.entities.job import Job
from services.ai_api.domain.enums.job_status import JobStatus
from services.ai_api.domain.interfaces.job_repository import IJobRepository
from services.ai_api.infrastructure.persistence.models.job_model import JobModel


class SQLAlchemyJobRepository(IJobRepository):
    """Concrete job repository backed by SQLAlchemy async sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, job: Job) -> Job:
        """Persist a new job."""
        model = JobModel.from_entity(job)
        self._session.add(model)
        await self._session.flush()
        return model.to_entity()

    async def get_by_id(self, job_id: str) -> Job | None:
        """Retrieve a job by ID."""
        result = await self._session.get(JobModel, job_id)
        return result.to_entity() if result else None

    async def update(self, job: Job) -> Job:
        """Update an existing job."""
        model = await self._session.get(JobModel, job.id)
        if model is None:
            raise ValueError(f"Job {job.id} not found for update")

        model.status = job.status.value
        model.progress = job.progress
        model.stage = job.stage
        model.result_url = job.result_url
        model.error_message = job.error_message
        model.input_params_json = json.dumps(job.input_params, default=str)
        model.updated_at = job.updated_at

        await self._session.flush()
        return model.to_entity()

    async def list_by_status(self, status: JobStatus, limit: int = 50) -> list[Job]:
        """List jobs filtered by status."""
        stmt = (
            select(JobModel)
            .where(JobModel.status == status.value)
            .order_by(JobModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [row.to_entity() for row in result.scalars().all()]

    async def delete(self, job_id: str) -> bool:
        """Delete a job by ID."""
        model = await self._session.get(JobModel, job_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True
