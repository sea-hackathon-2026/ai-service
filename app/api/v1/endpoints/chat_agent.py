"""
Chat Agent Endpoint — FastAPI integration for the ADK Sales Agent.

Provides REST endpoints for the frontend to interact with the sales
closing agent via HTTP. Session state is maintained in-memory per
session_id.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent Chat"])


# ── Request / Response Models ────────────────────────────────────────
class ChatRequest(BaseModel):
    """Incoming chat message from the frontend."""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Agent response returned to the frontend."""
    reply: str
    session_id: str
    order_status: Optional[dict] = None


class ResetResponse(BaseModel):
    """Response after session reset."""
    session_id: str
    message: str


# ── Lazy Agent Loader ────────────────────────────────────────────────
_runner = None
_session_service = None
_AGENT_DIR = Path(__file__).resolve().parents[4] / "agent-sales"


def _ensure_agent_loaded():
    """Lazy-load the ADK agent and runner on first request."""
    global _runner, _session_service

    if _runner is not None:
        return

    import os
    from dotenv import load_dotenv

    # Load agent .env (GOOGLE_API_KEY)
    env_path = _AGENT_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)

    # Bootstrap the hyphenated package
    pkg_name = "agent_sales_pkg"
    if pkg_name not in sys.modules:
        # tools
        tools_spec = importlib.util.spec_from_file_location(
            f"{pkg_name}.tools", _AGENT_DIR / "tools.py",
        )
        tools_mod = importlib.util.module_from_spec(tools_spec)
        sys.modules[f"{pkg_name}.tools"] = tools_mod
        tools_spec.loader.exec_module(tools_mod)

        # package
        pkg_spec = importlib.util.spec_from_file_location(
            pkg_name, _AGENT_DIR / "__init__.py",
            submodule_search_locations=[str(_AGENT_DIR)],
        )
        pkg_mod = importlib.util.module_from_spec(pkg_spec)
        pkg_mod.tools = tools_mod
        sys.modules[pkg_name] = pkg_mod

        # agent
        agent_spec = importlib.util.spec_from_file_location(
            f"{pkg_name}.agent", _AGENT_DIR / "agent.py",
        )
        agent_mod = importlib.util.module_from_spec(agent_spec)
        sys.modules[f"{pkg_name}.agent"] = agent_mod
        agent_spec.loader.exec_module(agent_mod)
        pkg_mod.agent = agent_mod

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from agent_sales_pkg.agent import root_agent

    _session_service = InMemorySessionService()
    _runner = Runner(
        agent=root_agent,
        app_name="sales_closing_agent",
        session_service=_session_service,
    )

    logger.info("✅ Sales Agent loaded successfully")


# ── Endpoints ────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """Send a message to the sales agent and get a response.

    If no session_id is provided, a new session is created automatically.
    """
    _ensure_agent_loaded()

    from google.genai import types

    user_id = "api_user"

    # Create or reuse session
    session_id = request.session_id
    if not session_id:
        session = await _session_service.create_session(
            app_name="sales_closing_agent",
            user_id=user_id,
        )
        session_id = session.id
    else:
        # Verify session exists, create if not
        try:
            await _session_service.get_session(
                app_name="sales_closing_agent",
                user_id=user_id,
                session_id=session_id,
            )
        except Exception:
            session = await _session_service.create_session(
                app_name="sales_closing_agent",
                user_id=user_id,
            )
            session_id = session.id

    # Package user message
    content = types.Content(
        role="user",
        parts=[types.Part(text=request.message)],
    )

    # Collect agent response
    reply_parts: list[str] = []
    try:
        async for event in _runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        reply_parts.append(part.text)
    except Exception as exc:
        error_msg = str(exc)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            logger.warning("Gemini API rate limit: %s", exc)
            raise HTTPException(
                status_code=429,
                detail="Gemini API đã hết quota. Vui lòng đợi 1-2 phút rồi thử lại.",
            )
        elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
            logger.error("Gemini API key invalid: %s", exc)
            raise HTTPException(
                status_code=403,
                detail="API key không hợp lệ. Kiểm tra lại GOOGLE_API_KEY.",
            )
        logger.error("Agent error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    reply = "".join(reply_parts) or "Xin lỗi, tôi không thể trả lời lúc này."

    return ChatResponse(
        reply=reply,
        session_id=session_id,
    )


@router.post("/reset", response_model=ResetResponse)
async def reset_session():
    """Create a new chat session, discarding any previous conversation."""
    _ensure_agent_loaded()

    user_id = "api_user"
    session = await _session_service.create_session(
        app_name="sales_closing_agent",
        user_id=user_id,
    )

    return ResetResponse(
        session_id=session.id,
        message="Phiên chat đã được reset. Bắt đầu cuộc hội thoại mới!",
    )
