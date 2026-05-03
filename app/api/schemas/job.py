"""Job API schemas - Request and response models for job status queries."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class JobStatusResponse(BaseModel):
    """Response for job status queries."""

    id: str
    model_type: str
    status: str
    progress: float
    stage: str
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
