"""OpenAI adapter for grounded live-commerce script generation."""

from __future__ import annotations

import json
import time

from openai import OpenAI

from services.rag_service.domain.models import (
    ClassifiedComment,
    GeneratedScript,
    RetrievedDocument,
)


class ModelNotConfiguredError(RuntimeError):
    """Raised when generation is requested without provider credentials."""


class OpenAIScriptGenerator:
    """Generate structured scripts while keeping provider code out of the domain."""

    _SYSTEM_PROMPT = """You are a Vietnamese live-commerce presenter.
Answer only from the supplied product context. If the context is insufficient,
say that the information must be confirmed instead of inventing facts.
Return JSON with: text, emotion, call_to_action, confidence."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def generate(
        self,
        comments: list[ClassifiedComment],
        documents: list[RetrievedDocument],
    ) -> GeneratedScript:
        if not self.configured:
            raise ModelNotConfiguredError("RAG_OPENAI_API_KEY is not configured")

        prompt = {
            "comments": [comment.text for comment in comments],
            "intent": comments[0].intent.value,
            "context": [{"tag": document.tag, "text": document.text} for document in documents],
        }
        started_at = time.perf_counter()
        response = OpenAI(api_key=self._api_key).chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": self._SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        payload = json.loads(response.choices[0].message.content or "{}")
        intent = comments[0].intent
        return GeneratedScript(
            text=str(payload.get("text", "")),
            intent=intent,
            emotion=str(payload.get("emotion", "friendly")),
            call_to_action=str(payload.get("call_to_action", "engage")),
            confidence=float(payload.get("confidence", 0.8)),
            source_comments=tuple(comment.text for comment in comments),
            retrieved_tags=tuple(document.tag for document in documents),
            latency_ms=latency_ms,
        )
