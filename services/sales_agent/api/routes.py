"""Sales-agent REST endpoints."""

from fastapi import APIRouter, Depends

from services.sales_agent.api.dependencies import get_runtime
from services.sales_agent.api.schemas import ChatRequest, ChatResponse, ResetResponse
from services.sales_agent.infrastructure.adk_runtime import SalesAgentRuntime

router = APIRouter()


@router.get("/health", tags=["operations"])
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "sales-agent"}


@router.post("/v1/chat", response_model=ChatResponse, tags=["agent"])
async def chat(
    request: ChatRequest,
    runtime: SalesAgentRuntime = Depends(get_runtime),
) -> ChatResponse:
    reply, session_id, fallback_used = await runtime.chat(request.message, request.session_id)
    return ChatResponse(reply=reply, session_id=session_id, fallback_used=fallback_used)


@router.post("/v1/sessions/reset", response_model=ResetResponse, tags=["agent"])
async def reset(
    runtime: SalesAgentRuntime = Depends(get_runtime),
) -> ResetResponse:
    return ResetResponse(session_id=await runtime.reset())
