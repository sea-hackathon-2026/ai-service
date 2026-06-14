"""Ports implemented by external RAG infrastructure."""

from __future__ import annotations

from typing import Protocol

from services.rag_service.domain.models import (
    ClassifiedComment,
    GeneratedScript,
    RetrievedDocument,
)


class KnowledgeRepository(Protocol):
    """Searches product knowledge without exposing storage details."""

    def search(self, query: str, top_k: int) -> list[RetrievedDocument]: ...


class ScriptGenerator(Protocol):
    """Generates one grounded presenter response."""

    def generate(
        self,
        comments: list[ClassifiedComment],
        documents: list[RetrievedDocument],
    ) -> GeneratedScript: ...
