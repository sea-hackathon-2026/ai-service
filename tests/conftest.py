"""Shared fixtures for service-level integration tests."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Settings must exist before importing modules that compose global adapters.
os.environ["AI_API_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["AI_API_API_KEY_SECRET"] = "test-api-key"
os.environ["AI_API_DEBUG"] = "true"
os.environ["AI_API_STORAGE_LOCAL_PATH"] = "./data/test-outputs"

from services.ai_api.infrastructure.persistence.database import (  # noqa: E402
    Base,
    get_async_session,
)
from services.ai_api.infrastructure.persistence.models.job_model import (  # noqa: E402,F401
    JobModel,
)
from services.ai_api.main import app  # noqa: E402

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
test_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def _test_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP client whose repository uses the test database."""

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    app.dependency_overrides[get_async_session] = _test_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client

    app.dependency_overrides.clear()
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture
def api_key_header() -> dict[str, str]:
    return {"X-API-Key": "test-api-key"}
