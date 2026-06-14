"""FastAPI application factory for the sales-agent service."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from services.sales_agent.api.routes import router
from services.sales_agent.config import get_settings
from services.sales_agent.infrastructure.adk_runtime import AgentRuntimeError


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Live-Commerce Sales Agent",
        version=settings.service_version,
        description="Stateful Google ADK agent for consultation and order closing.",
    )
    application.include_router(router)

    @application.exception_handler(AgentRuntimeError)
    async def runtime_error(request: Request, exc: AgentRuntimeError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    return application


app = create_app()
