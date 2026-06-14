"""In-memory TF-IDF retrieval over a JSON product knowledge base."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from services.rag_service.domain.models import RetrievedDocument


def _render_value(value: Any) -> str:
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_render_value(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "; ".join(_render_value(item) for item in value)
    return str(value)


def _to_chunks(payload: dict[str, Any]) -> list[tuple[str, str]]:
    """Create explainable chunks using top-level knowledge sections as tags."""

    return [
        (key, f"{key.replace('_', ' ')}: {_render_value(value)}")
        for key, value in payload.items()
        if value not in (None, "", [], {})
    ]


class JsonKnowledgeRepository:
    """Small-corpus retrieval adapter with no vector database dependency."""

    def __init__(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self._chunks = _to_chunks(payload)
        self._tokens = [Counter(self._tokenize(text)) for _, text in self._chunks]
        self._idf = self._build_idf()
        self._vectors = [self._vectorize(tokens) for tokens in self._tokens]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        normalized = re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE)
        return [token for token in normalized.split() if len(token) > 1]

    def _build_idf(self) -> dict[str, float]:
        document_count = len(self._tokens)
        frequencies: Counter[str] = Counter()
        for tokens in self._tokens:
            frequencies.update(tokens.keys())
        return {
            token: math.log((1 + document_count) / (1 + count)) + 1
            for token, count in frequencies.items()
        }

    def _vectorize(self, tokens: Counter[str]) -> dict[str, float]:
        total = sum(tokens.values()) or 1
        return {
            token: (count / total) * self._idf.get(token, 1.0) for token, count in tokens.items()
        }

    @staticmethod
    def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
        dot = sum(value * right.get(token, 0.0) for token, value in left.items())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    def search(self, query: str, top_k: int) -> list[RetrievedDocument]:
        query_vector = self._vectorize(Counter(self._tokenize(query)))
        ranked = sorted(
            (
                (index, self._cosine(query_vector, vector))
                for index, vector in enumerate(self._vectors)
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        return [
            RetrievedDocument(
                tag=self._chunks[index][0],
                text=self._chunks[index][1],
                score=round(score, 4),
            )
            for index, score in ranked[:top_k]
            if score > 0
        ]
