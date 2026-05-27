"""
FastAPI application for Sales Closing Agent.
Provides REST endpoints and handles Groq fallback when Gemini quota is exhausted.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models import registry
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

# Cần đăng ký tiền tố cho LiteLLM để ADK không báo lỗi "Model not found"
registry.LLMRegistry._register(r"^groq/.*", LiteLlm)
registry.LLMRegistry._register(r"^openrouter/.*", LiteLlm)
registry.LLMRegistry._register(r"^huggingface/.*", LiteLlm)

from agent import root_agent

# Try to load environment variables
load_dotenv()
load_dotenv("../.env", override=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sales Closing Agent API",
    description="Agent API with Gemini and Groq fallback",
    version="1.0.0",
)

# ── Session Management ──────────────────────────────────────────────────
_session_service = InMemorySessionService()

# Maintain two runners: primary (Gemini) and fallback (Groq)
# We will lazily initialize the fallback runner if needed.
_primary_runner = Runner(
    agent=root_agent,
    app_name="sales_closing_agent",
    session_service=_session_service,
)
_fallback_runner = None


def get_fallback_runner() -> Runner:
    """Lazy initialize the fallback runner using Groq via LiteLLM."""
    global _fallback_runner
    if _fallback_runner is not None:
        return _fallback_runner

    if not os.environ.get("HUGGINGFACE_API_KEY") and not os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("GROQ_API_KEY"):
        logger.error("Không có API Key nào cho fallback (HuggingFace, OpenRouter, Groq).")
        raise ValueError("Missing API keys for fallback")

    # In ADK, we can create a new Agent object pointing to litellm
    from google.adk.agents import Agent
    import tools
    
    # Ưu tiên HuggingFace -> OpenRouter -> Groq
    if os.environ.get("HUGGINGFACE_API_KEY"):
        model_name = "huggingface/deepseek-ai/DeepSeek-V3" # Bạn có thể đổi tên model tùy ý
    elif os.environ.get("OPENROUTER_API_KEY"):
        model_name = "openrouter/deepseek/deepseek-v4-flash:free"
    else:
        model_name = "groq/llama-3.3-70b-versatile"
    
    # Re-use the same instruction and tools, but change the model
    fallback_agent = Agent(
        name="sales_closing_agent_fallback",
        model=model_name,
        description=root_agent.description,
        instruction=root_agent.instruction,
        tools=[tools.save_order_info, tools.get_order_status, tools.confirm_order],
    )

    _fallback_runner = Runner(
        agent=fallback_agent,
        app_name="sales_closing_agent",
        session_service=_session_service,
    )
    logger.info("Initialized Groq fallback runner")
    return _fallback_runner


# ── Request / Response Models ──────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    fallback_used: bool = False


class ResetResponse(BaseModel):
    session_id: str
    message: str


# ── Endpoints ──────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    user_id = "api_user"

    # 1. Resolve Session
    session_id = request.session_id
    if not session_id:
        session = await _session_service.create_session(
            app_name="sales_closing_agent",
            user_id=user_id,
        )
        session_id = session.id
    else:
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

    content = types.Content(
        role="user",
        parts=[types.Part(text=request.message)],
    )

    reply_parts: list[str] = []
    fallback_used = False

    # 2. Try Primary Runner (Gemini)
    try:
        async for event in _primary_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            if event.content and event.content.parts and event.is_final_response():
                for part in event.content.parts:
                    if part.text:
                        reply_parts.append(part.text)
    except Exception as exc:
        error_msg = str(exc)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            logger.warning("Gemini 429 Quota Exceeded. Attempting Groq fallback...")
            fallback_used = True
        else:
            # Re-raise if it's not a rate limit issue
            logger.error(f"Primary agent failed: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    # 3. Fallback to Groq if Primary Failed
    if fallback_used:
        try:
            fallback_runner = get_fallback_runner()
            # Reset reply parts since we are re-running
            reply_parts = []
            
            # Note: We send the same message to the same session_id,
            # ADK's session memory will just process it using the new agent model
            async for event in fallback_runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
            ):
                if event.content and event.content.parts and event.is_final_response():
                    for part in event.content.parts:
                        if part.text:
                            reply_parts.append(part.text)
        except Exception as fallback_exc:
            logger.error(f"Fallback agent also failed: {fallback_exc}")
            raise HTTPException(
                status_code=503, 
                detail=f"Cả Gemini và Groq đều lỗi. Lỗi Groq: {fallback_exc}"
            )

    reply = "".join(reply_parts) or "Xin lỗi, tôi không thể trả lời lúc này."

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        fallback_used=fallback_used,
    )


@app.post("/reset", response_model=ResetResponse)
async def reset_session():
    user_id = "api_user"
    session = await _session_service.create_session(
        app_name="sales_closing_agent",
        user_id=user_id,
    )

    return ResetResponse(
        session_id=session.id,
        message="Đã reset phiên chat.",
    )
