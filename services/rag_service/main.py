"""FastAPI application factory for the standalone RAG service."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from services.rag_service.api.routes import router
from services.rag_service.config import get_settings
from services.rag_service.infrastructure.openai_script_generator import (
    ModelNotConfiguredError,
)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Live-Commerce RAG Service",
        version=settings.service_version,
        description="Grounded retrieval and script generation for livestream comments.",
    )
    application.include_router(router)

    @application.exception_handler(ModelNotConfiguredError)
    async def model_not_configured(
        request: Request,
        exc: ModelNotConfiguredError,
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    return application


app = create_app()
