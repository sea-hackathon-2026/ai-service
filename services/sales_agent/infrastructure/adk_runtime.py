"""Stateful Google ADK runtime with provider fallback."""

from __future__ import annotations

import logging
import os

from google.adk.models import registry
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from services.sales_agent.agent import build_agent
from services.sales_agent.config import Settings

logger = logging.getLogger(__name__)


class AgentRuntimeError(RuntimeError):
    """Raised when model execution cannot produce a response."""


class SalesAgentRuntime:
    """Own ADK sessions and hide provider execution from the API layer."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sessions = InMemorySessionService()
        self._register_litellm_adapters()
        self._primary = Runner(
            agent=build_agent(settings.primary_model),
            app_name=settings.service_name,
            session_service=self._sessions,
        )
        self._fallback: Runner | None = None

    @staticmethod
    def _register_litellm_adapters() -> None:
        for prefix in ("groq", "openrouter", "huggingface"):
            registry.LLMRegistry._register(rf"^{prefix}/.*", LiteLlm)

    async def _ensure_session(self, session_id: str | None) -> str:
        if session_id:
            session = await self._sessions.get_session(
                app_name=self._settings.service_name,
                user_id=self._settings.user_id,
                session_id=session_id,
            )
            if session is not None:
                return session_id
        session = await self._sessions.create_session(
            app_name=self._settings.service_name,
            user_id=self._settings.user_id,
        )
        return session.id

    async def _run(self, runner: Runner, session_id: str, message: str) -> str:
        content = types.Content(role="user", parts=[types.Part(text=message)])
        reply: list[str] = []
        async for event in runner.run_async(
            user_id=self._settings.user_id,
            session_id=session_id,
            new_message=content,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                reply.extend(part.text for part in event.content.parts if part.text)
        return "".join(reply)

    def _get_fallback_runner(self) -> Runner:
        if self._fallback is not None:
            return self._fallback
        if self._settings.fallback_model.startswith("groq/") and not os.getenv("GROQ_API_KEY"):
            raise AgentRuntimeError("GROQ_API_KEY is required for the fallback model")
        self._fallback = Runner(
            agent=build_agent(
                self._settings.fallback_model,
                name="sales_closing_agent_fallback",
            ),
            app_name=self._settings.service_name,
            session_service=self._sessions,
        )
        return self._fallback

    async def chat(self, message: str, session_id: str | None) -> tuple[str, str, bool]:
        resolved_session_id = await self._ensure_session(session_id)
        try:
            reply = await self._run(self._primary, resolved_session_id, message)
            return reply, resolved_session_id, False
        except Exception as primary_error:
            error_text = str(primary_error).upper()
            if "429" not in error_text and "RESOURCE_EXHAUSTED" not in error_text:
                raise AgentRuntimeError("Primary agent execution failed") from primary_error
            logger.warning("Primary model quota exhausted; using fallback model")

        try:
            reply = await self._run(self._get_fallback_runner(), resolved_session_id, message)
            return reply, resolved_session_id, True
        except Exception as fallback_error:
            raise AgentRuntimeError(
                "Primary and fallback agent execution failed"
            ) from fallback_error

    async def reset(self) -> str:
        session = await self._sessions.create_session(
            app_name=self._settings.service_name,
            user_id=self._settings.user_id,
        )
        return session.id
