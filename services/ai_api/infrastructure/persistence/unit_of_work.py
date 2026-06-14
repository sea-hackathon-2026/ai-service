"""SQLAlchemy implementation of the job transaction boundary."""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from services.ai_api.domain.interfaces.job_repository import IJobRepository
from services.ai_api.domain.interfaces.job_unit_of_work import IJobUnitOfWork
from services.ai_api.infrastructure.persistence.database import async_session_factory
from services.ai_api.infrastructure.persistence.repositories.job_repository import (
    SQLAlchemyJobRepository,
)


class SQLAlchemyJobUnitOfWork(IJobUnitOfWork):
    """Create one session and repository per application transaction."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
    ) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.jobs: IJobRepository

    async def __aenter__(self) -> SQLAlchemyJobUnitOfWork:
        self._session = self._session_factory()
        self.jobs = SQLAlchemyJobRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        if exc_type is not None:
            await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of work has not been entered")
        await self._session.commit()
