"""Transaction boundary for job persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType

from services.ai_api.domain.interfaces.job_repository import IJobRepository


class IJobUnitOfWork(ABC):
    """Expose job persistence without coupling use cases to SQLAlchemy."""

    jobs: IJobRepository

    @abstractmethod
    async def __aenter__(self) -> IJobUnitOfWork: ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...
