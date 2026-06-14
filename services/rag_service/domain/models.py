"""Domain models used by the RAG pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Intent(StrEnum):
    """Supported live-commerce audience intents."""

    PRICE = "price"
    PRODUCT = "product"
    SHIPPING = "shipping"
    PROMOTION = "promotion"
    HEALTH = "health"
    SHELF_LIFE = "shelf_life"
    ORDER = "order"
    RESTOCK = "restock"
    GENERAL = "general"
    NOISE = "noise"


@dataclass(frozen=True, slots=True)
class AudienceComment:
    """A normalized comment received from a livestream platform."""

    text: str
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class ClassifiedComment:
    """A comment enriched with deterministic intent metadata."""

    text: str
    intent: Intent
    score: float
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievedDocument:
    """A knowledge chunk and its retrieval relevance score."""

    tag: str
    text: str
    score: float


@dataclass(frozen=True, slots=True)
class GeneratedScript:
    """Grounded presenter response generated for one comment batch."""

    text: str
    intent: Intent
    emotion: str
    call_to_action: str
    confidence: float
    source_comments: tuple[str, ...]
    retrieved_tags: tuple[str, ...]
    latency_ms: int
