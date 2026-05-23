"""
FastAPI dependency injection functions.

Provides injectable dependencies for database sessions, services,
repositories, and use cases following the dependency inversion principle.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.security import verify_api_key
from app.infrastructure.persistence.database import get_async_session
from app.infrastructure.persistence.repositories.job_repository import (
    SQLAlchemyJobRepository,
)
from app.infrastructure.ai_models.video_generator import MockVideoGenerator
from app.infrastructure.ai_models.tts_engine import MockTTSEngine
from app.infrastructure.ai_models.micro_scene_pipeline import MicroScenePipelineConfig
from app.infrastructure.storage.local_storage import LocalStorageService
from app.application.use_cases.generate_livestream_video import (
    GenerateLivestreamVideoUseCase,
)
from app.application.use_cases.generate_video import GenerateVideoUseCase
from app.application.use_cases.text_to_speech import TextToSpeechUseCase
from app.application.use_cases.get_job_status import GetJobStatusUseCase
from app.domain.interfaces.video_service import IVideoService
from app.domain.interfaces.tts_service import ITTSService
from app.domain.interfaces.job_repository import IJobRepository
from app.domain.interfaces.storage_service import IStorageService


# ── Settings ──
SettingsDep = Annotated[Settings, Depends(get_settings)]

# ── Database Session ──
SessionDep = Annotated[AsyncSession, Depends(get_async_session)]


# ── Auth ──
async def verify_api_key_header(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> str:
    """Validate API key from request header."""
    if not verify_api_key(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return x_api_key


ApiKeyDep = Annotated[str, Depends(verify_api_key_header)]


# ── Services (singletons — lazy initialized) ──

_video_service: IVideoService | None = None
_tts_service: ITTSService | None = None
_storage_service: IStorageService | None = None


def get_video_service() -> IVideoService:
    """Get the video generation service (singleton)."""
    global _video_service
    if _video_service is None:
        _video_service = MockVideoGenerator()
    return _video_service


def get_tts_service() -> ITTSService:
    """Get the TTS service (singleton)."""
    global _tts_service
    if _tts_service is None:
        _tts_service = MockTTSEngine()
    return _tts_service


def get_storage_service() -> IStorageService:
    """Get the storage service (singleton)."""
    global _storage_service
    if _storage_service is None:
        settings = get_settings()
        _storage_service = LocalStorageService(settings.storage_local_path)
    return _storage_service


VideoServiceDep = Annotated[IVideoService, Depends(get_video_service)]
TTSServiceDep = Annotated[ITTSService, Depends(get_tts_service)]
StorageDep = Annotated[IStorageService, Depends(get_storage_service)]


# ── Repositories ──


def get_job_repository(session: SessionDep) -> IJobRepository:
    """Get job repository with injected session."""
    return SQLAlchemyJobRepository(session)


JobRepoDep = Annotated[IJobRepository, Depends(get_job_repository)]


# ── Use Cases ──


def get_generate_video_use_case(
    video_service: VideoServiceDep,
    job_repo: JobRepoDep,
    storage: StorageDep,
) -> GenerateVideoUseCase:
    """Assemble the video generation use case with all dependencies."""
    return GenerateVideoUseCase(video_service, job_repo, storage)


def get_livestream_video_use_case(
    job_repo: JobRepoDep,
    settings: SettingsDep,
) -> GenerateLivestreamVideoUseCase:
    """Assemble the micro-scene livestream video use case."""
    pipeline_config = MicroScenePipelineConfig(
        output_width=settings.livestream_output_width,
        output_height=settings.livestream_output_height,
        fps=settings.livestream_fps,
        tts_provider=settings.livestream_tts_provider,
        tts_voice=settings.livestream_tts_voice,
        enable_wav2lip=settings.livestream_enable_wav2lip,
        wav2lip_dir=settings.wav2lip_dir,
        wav2lip_checkpoint=settings.wav2lip_checkpoint,
        wav2lip_resize_factor=settings.wav2lip_resize_factor,
        wav2lip_pads=settings.wav2lip_pads,
    )
    return GenerateLivestreamVideoUseCase(
        job_repository=job_repo,
        pipeline_config=pipeline_config,
        public_url_prefix="/static/outputs",
    )


def get_tts_use_case(
    tts_service: TTSServiceDep,
    job_repo: JobRepoDep,
    storage: StorageDep,
) -> TextToSpeechUseCase:
    """Assemble the TTS use case with all dependencies."""
    return TextToSpeechUseCase(tts_service, job_repo, storage)


def get_job_status_use_case(
    job_repo: JobRepoDep,
) -> GetJobStatusUseCase:
    """Assemble the job status use case."""
    return GetJobStatusUseCase(job_repo)


VideoUseCaseDep = Annotated[GenerateVideoUseCase, Depends(get_generate_video_use_case)]
LivestreamVideoUseCaseDep = Annotated[
    GenerateLivestreamVideoUseCase,
    Depends(get_livestream_video_use_case),
]
TTSUseCaseDep = Annotated[TextToSpeechUseCase, Depends(get_tts_use_case)]
JobStatusUseCaseDep = Annotated[GetJobStatusUseCase, Depends(get_job_status_use_case)]
