"""
Async SQLAlchemy database engine and session management.

Provides the async engine, session factory, and base model class.
Supports SQLite (dev) and PostgreSQL (prod) via DATABASE_URL config.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from services.ai_api.config import get_settings

settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    # SQLite-specific: allow async usage
    connect_args=({"check_same_thread": False} if "sqlite" in settings.database_url else {}),
)

# Async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""

    pass


async def get_async_session() -> AsyncSession:
    """
    Dependency-injectable async session generator.

    Usage in FastAPI:
        session: AsyncSession = Depends(get_async_session)
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables. Called during application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the engine. Called during application shutdown."""
    await engine.dispose()
