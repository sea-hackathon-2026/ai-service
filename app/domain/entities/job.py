"""
Job entity - Represents an AI processing job (video gen or TTS).

A Job tracks the lifecycle of a user request from creation through
processing to completion or failure, including progress updates.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.domain.enums.job_status import JobStatus
from app.domain.enums.model_type import ModelType


@dataclass
class Job:
    """Domain entity representing an AI processing job."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_type: ModelType = ModelType.VIDEO_GEN
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0  # 0.0 → 1.0
    stage: str = "queued"
    input_params: Dict[str, Any] = field(default_factory=dict)
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def start_processing(self) -> None:
        """Transition job to processing state."""
        self.status = JobStatus.PROCESSING
        self.stage = "initializing"
        self.updated_at = datetime.now(timezone.utc)

    def update_progress(self, progress: float, stage: str) -> None:
        """Update job progress (0.0 to 1.0) and current stage description."""
        self.progress = min(max(progress, 0.0), 1.0)
        self.stage = stage
        self.status = JobStatus.STREAMING
        self.updated_at = datetime.now(timezone.utc)

    def complete(self, result_url: str) -> None:
        """Mark job as successfully completed."""
        self.status = JobStatus.DONE
        self.progress = 1.0
        self.stage = "completed"
        self.result_url = result_url
        self.updated_at = datetime.now(timezone.utc)

    def fail(self, error_message: str) -> None:
        """Mark job as failed with an error message."""
        self.status = JobStatus.FAILED
        self.stage = "failed"
        self.error_message = error_message
        self.updated_at = datetime.now(timezone.utc)

    @property
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state (DONE or FAILED)."""
        return self.status in (JobStatus.DONE, JobStatus.FAILED)
