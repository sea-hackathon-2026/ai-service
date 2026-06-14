"""Use cases that orchestrate the live-comment RAG pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from services.rag_service.application.ports import KnowledgeRepository, ScriptGenerator
from services.rag_service.domain.batching import batch_by_intent
from services.rag_service.domain.classification import classify_actionable_comments
from services.rag_service.domain.models import (
    AudienceComment,
    GeneratedScript,
    RetrievedDocument,
)


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Result of processing one group of audience comments."""

    received_count: int
    filtered_count: int
    scripts: tuple[GeneratedScript, ...]


class SearchKnowledge:
    """Retrieve knowledge chunks for diagnostics and evaluation."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self._repository = repository

    def execute(self, query: str, top_k: int = 3) -> list[RetrievedDocument]:
        return self._repository.search(query=query, top_k=top_k)


class GenerateGroundedScripts:
    """Filter, classify, batch, retrieve, and generate presenter scripts."""

    def __init__(
        self,
        repository: KnowledgeRepository,
        generator: ScriptGenerator,
    ) -> None:
        self._repository = repository
        self._generator = generator

    def execute(
        self,
        comments: list[AudienceComment],
        top_k: int = 3,
        max_batch_size: int = 4,
    ) -> PipelineResult:
        actionable = classify_actionable_comments(comments)
        scripts: list[GeneratedScript] = []
        for batch in batch_by_intent(actionable, max_batch_size=max_batch_size):
            query = " ".join(comment.text for comment in batch)
            documents = self._repository.search(query=query, top_k=top_k)
            scripts.append(self._generator.generate(batch, documents))

        return PipelineResult(
            received_count=len(comments),
            filtered_count=len(comments) - len(actionable),
            scripts=tuple(scripts),
        )
