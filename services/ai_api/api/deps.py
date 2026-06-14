"""
FastAPI dependency injection functions.

Provides injectable dependencies for database sessions, services,
repositories, and use cases following the dependency inversion principle.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_api.application.use_cases.generate_livestream_video import (
    GenerateLivestreamVideoUseCase,
)
from services.ai_api.application.use_cases.generate_video import GenerateVideoUseCase
from services.ai_api.application.use_cases.get_job_status import GetJobStatusUseCase
from services.ai_api.application.use_cases.text_to_speech import TextToSpeechUseCase
from services.ai_api.config import Settings, get_settings
from services.ai_api.core.security import verify_api_key
from services.ai_api.domain.interfaces.job_repository import IJobRepository
from services.ai_api.domain.interfaces.storage_service import IStorageService
from services.ai_api.domain.interfaces.tts_service import ITTSService
from services.ai_api.domain.interfaces.video_service import IVideoService
from services.ai_api.infrastructure.ai_models.micro_scene_pipeline import (
    MicroScenePipelineConfig,
    MicroSceneVideoPipeline,
)
from services.ai_api.infrastructure.ai_models.tts_engine import MockTTSEngine
from services.ai_api.infrastructure.ai_models.video_generator import MockVideoGenerator
from services.ai_api.infrastructure.persistence.database import (
    async_session_factory,
    get_async_session,
)
from services.ai_api.infrastructure.persistence.repositories.job_repository import (
    SQLAlchemyJobRepository,
)
from services.ai_api.infrastructure.persistence.unit_of_work import (
    SQLAlchemyJobUnitOfWork,
)
from services.ai_api.infrastructure.storage.local_storage import LocalStorageService

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
    settings: SettingsDep,
) -> GenerateLivestreamVideoUseCase:
    """Assemble the micro-scene livestream video use case.

    When ``GEMINI_API_KEY`` is set and ``GENAI_PREFER_API`` is True,
    a :class:`GeminiGenAIClient` is injected so the pipeline tries the
    Google GenAI path before falling back to local FFmpeg.
    """
    # ── Optionally create GenAI client ──
    genai_client = None
    if settings.gemini_api_key and settings.genai_prefer_api:
        try:
            from services.ai_api.infrastructure.ai_models.gemini_genai_client import (
                GeminiGenAIClient,
            )

            genai_client = GeminiGenAIClient(
                api_key=settings.gemini_api_key,
                imagen_model=settings.genai_imagen_model,
                veo_model=settings.genai_veo_model,
            )
        except ImportError:
            pass  # google-genai not installed; stay local

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
        genai_client=genai_client,
        genai_aspect_ratio=settings.genai_aspect_ratio,
        genai_use_imagen=settings.genai_use_imagen,
        genai_skip_wav2lip=settings.genai_skip_wav2lip,
        genai_enhance_prompt=settings.genai_enhance_prompt,
    )
    return GenerateLivestreamVideoUseCase(
        unit_of_work_factory=SQLAlchemyJobUnitOfWork,
        pipeline_factory=lambda: MicroSceneVideoPipeline(
            config=pipeline_config,
            public_url_prefix="/outputs",
        ),
        public_url_prefix="/outputs",
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


@asynccontextmanager
async def video_stream_use_case() -> AsyncIterator[GenerateVideoUseCase]:
    """Provide a transaction-scoped use case for a WebSocket generation stream."""

    async with async_session_factory() as session:
        try:
            yield GenerateVideoUseCase(
                get_video_service(),
                SQLAlchemyJobRepository(session),
                get_storage_service(),
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def tts_stream_use_case() -> AsyncIterator[TextToSpeechUseCase]:
    """Provide a transaction-scoped use case for a WebSocket synthesis stream."""

    async with async_session_factory() as session:
        try:
            yield TextToSpeechUseCase(
                get_tts_service(),
                SQLAlchemyJobRepository(session),
                get_storage_service(),
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise


VideoUseCaseDep = Annotated[GenerateVideoUseCase, Depends(get_generate_video_use_case)]
LivestreamVideoUseCaseDep = Annotated[
    GenerateLivestreamVideoUseCase,
    Depends(get_livestream_video_use_case),
]
TTSUseCaseDep = Annotated[TextToSpeechUseCase, Depends(get_tts_use_case)]
JobStatusUseCaseDep = Annotated[GetJobStatusUseCase, Depends(get_job_status_use_case)]
