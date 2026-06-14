"""
JobModel - SQLAlchemy ORM model for the jobs table.

Maps between the domain Job entity and the database representation.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from services.ai_api.domain.entities.job import Job
from services.ai_api.domain.enums.job_status import JobStatus
from services.ai_api.domain.enums.model_type import ModelType
from services.ai_api.infrastructure.persistence.database import Base


class JobModel(Base):
    """ORM model for AI processing jobs."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ModelType.VIDEO_GEN.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=JobStatus.PENDING.value, index=True
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    stage: Mapped[str] = mapped_column(String(100), default="queued")
    input_params_json: Mapped[str] = mapped_column(Text, default="{}")
    result_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def to_entity(self) -> Job:
        """Convert ORM model to domain entity."""
        return Job(
            id=self.id,
            model_type=ModelType(self.model_type),
            status=JobStatus(self.status),
            progress=self.progress,
            stage=self.stage,
            input_params=json.loads(self.input_params_json) if self.input_params_json else {},
            result_url=self.result_url,
            error_message=self.error_message,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: Job) -> JobModel:
        """Create ORM model from domain entity."""
        return cls(
            id=entity.id,
            model_type=entity.model_type.value,
            status=entity.status.value,
            progress=entity.progress,
            stage=entity.stage,
            input_params_json=json.dumps(entity.input_params, default=str),
            result_url=entity.result_url,
            error_message=entity.error_message,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
