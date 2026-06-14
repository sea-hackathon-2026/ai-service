"""
Job status REST endpoints.

GET /v1/jobs/{job_id} - get current status and progress of a job.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.ai_api.api.deps import ApiKeyDep, JobStatusUseCaseDep
from services.ai_api.api.schemas.job import JobStatusResponse
from services.ai_api.domain.exceptions.base import EntityNotFoundError

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description="Query the current status and progress of an AI processing job.",
)
async def get_job_status(
    job_id: str,
    use_case: JobStatusUseCaseDep,
    _api_key: ApiKeyDep,
) -> JobStatusResponse:
    """Get job status by ID."""
    try:
        job = await use_case.execute(job_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found") from exc

    return JobStatusResponse(
        id=job.id,
        model_type=job.model_type.value,
        status=job.status.value,
        progress=job.progress,
        stage=job.stage,
        result_url=job.result_url,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
