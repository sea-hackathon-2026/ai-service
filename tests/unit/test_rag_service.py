"""Unit tests for deterministic RAG policies and orchestration."""

from pathlib import Path

from services.rag_service.application.use_cases import GenerateGroundedScripts
from services.rag_service.domain.batching import batch_by_intent
from services.rag_service.domain.classification import classify_actionable_comments
from services.rag_service.domain.models import (
    AudienceComment,
    GeneratedScript,
    Intent,
)
from services.rag_service.infrastructure.json_knowledge_repository import (
    JsonKnowledgeRepository,
)


class FakeGenerator:
    def generate(self, comments, documents):
        return GeneratedScript(
            text="Grounded response",
            intent=comments[0].intent,
            emotion="friendly",
            call_to_action="engage",
            confidence=0.9,
            source_comments=tuple(comment.text for comment in comments),
            retrieved_tags=tuple(document.tag for document in documents),
            latency_ms=1,
        )


def test_classification_filters_noise_and_detects_order_intent() -> None:
    comments = [
        AudienceComment("ok"),
        AudienceComment("Mình muốn đặt hàng sản phẩm này"),
    ]

    result = classify_actionable_comments(comments)

    assert len(result) == 1
    assert result[0].intent is Intent.ORDER


def test_batching_groups_same_intent() -> None:
    classified = classify_actionable_comments(
        [AudienceComment("Giá bao nhiêu?"), AudienceComment("Xin giá sản phẩm")]
    )

    batches = batch_by_intent(classified, max_batch_size=4)

    assert len(batches) == 1
    assert len(batches[0]) == 2


def test_pipeline_returns_grounded_script() -> None:
    repository = JsonKnowledgeRepository(Path("services/rag_service/resources/knowledge_base.json"))
    use_case = GenerateGroundedScripts(repository, FakeGenerator())

    result = use_case.execute([AudienceComment("Giá livestream bao nhiêu?")])

    assert result.received_count == 1
    assert len(result.scripts) == 1
    assert result.scripts[0].retrieved_tags
