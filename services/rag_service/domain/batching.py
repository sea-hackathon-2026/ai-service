"""Batching policy for reducing LLM calls during high-volume livestreams."""

from collections import defaultdict

from services.rag_service.domain.models import ClassifiedComment, Intent


def batch_by_intent(
    comments: list[ClassifiedComment],
    max_batch_size: int = 4,
) -> list[list[ClassifiedComment]]:
    """Group comments by intent while preserving first-seen intent order."""

    grouped: dict[Intent, list[ClassifiedComment]] = defaultdict(list)
    order: list[Intent] = []
    for comment in comments:
        if comment.intent not in grouped:
            order.append(comment.intent)
        grouped[comment.intent].append(comment)

    batches: list[list[ClassifiedComment]] = []
    for intent in order:
        values = grouped[intent]
        batches.extend(
            values[index : index + max_batch_size]
            for index in range(0, len(values), max_batch_size)
        )
    return batches
