"""Job API schemas - Request and response models for job status queries."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class JobStatusResponse(BaseModel):
    """Response for job status queries."""

    id: str
    model_type: str
    status: str
    progress: float
    stage: str
    result_url: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
