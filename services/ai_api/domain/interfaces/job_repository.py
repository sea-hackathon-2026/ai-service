"""
IJobRepository - Abstract interface for job persistence.

Provides CRUD operations for Job entities, decoupled from
the specific database implementation (SQLite, PostgreSQL, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from services.ai_api.domain.entities.job import Job
from services.ai_api.domain.enums.job_status import JobStatus


class IJobRepository(ABC):
    """Port for job data persistence."""

    @abstractmethod
    async def create(self, job: Job) -> Job:
        """Persist a new job and return it with any DB-assigned fields."""
        ...

    @abstractmethod
    async def get_by_id(self, job_id: str) -> Job | None:
        """Retrieve a job by its unique ID, or None if not found."""
        ...

    @abstractmethod
    async def update(self, job: Job) -> Job:
        """Update an existing job's state in the database."""
        ...

    @abstractmethod
    async def list_by_status(self, status: JobStatus, limit: int = 50) -> list[Job]:
        """List jobs filtered by status, ordered by creation time desc."""
        ...

    @abstractmethod
    async def delete(self, job_id: str) -> bool:
        """Delete a job by ID. Returns True if deleted, False if not found."""
        ...
