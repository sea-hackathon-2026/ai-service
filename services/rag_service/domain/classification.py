"""Deterministic filtering and intent classification policies."""

from __future__ import annotations

import re

from services.rag_service.domain.models import (
    AudienceComment,
    ClassifiedComment,
    Intent,
)

_INTENT_PATTERNS: dict[Intent, tuple[str, ...]] = {
    Intent.PRICE: (r"\bgi[aá]\b", r"bao nhi[eê]u", r"\bprice\b", r"\d+k\b"),
    Intent.PRODUCT: (r"c[oó] lo[aạ]i", r"m[uù]i", r"th[aà]nh ph[aầ]n", r"c[oô]ng d[uụ]ng"),
    Intent.SHIPPING: (r"\bship\b", r"giao h[aà]ng", r"ph[ií] v[aậ]n chuy[eể]n"),
    Intent.PROMOTION: (r"khuy[eế]n m[aã]i", r"ưu [đd][aã]i", r"\bdeal\b", r"gi[aả]m"),
    Intent.HEALTH: (r"mang thai", r"tr[eẻ] em", r"d[iị] [uứ]ng", r"an to[aà]n"),
    Intent.SHELF_LIFE: (r"h[aạ]n s[uử] d[uụ]ng", r"b[aả]o qu[aả]n", r"\bhsd\b"),
    Intent.ORDER: (r"[đd][aặ]t h[aà]ng", r"ch[oố]t [đd]ơn", r"mu[oố]n mua", r"\border\b"),
    Intent.RESTOCK: (r"c[oò]n h[aà]ng", r"h[eế]t h[aà]ng", r"khi n[aà]o v[eề]"),
}

_PRIORITY: dict[Intent, float] = {
    Intent.ORDER: 1.0,
    Intent.PRICE: 0.95,
    Intent.PROMOTION: 0.9,
    Intent.SHIPPING: 0.85,
    Intent.HEALTH: 0.85,
    Intent.RESTOCK: 0.8,
    Intent.SHELF_LIFE: 0.75,
    Intent.PRODUCT: 0.7,
    Intent.GENERAL: 0.4,
    Intent.NOISE: 0.0,
}


def _is_noise(text: str) -> bool:
    """Reject empty, emoji-only, and very short engagement comments."""

    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return True
    if normalized.lower() in {"hi", "hello", "ok", "haha", "wow", "up"}:
        return True
    return not any(character.isalnum() for character in normalized)


def classify_comment(comment: AudienceComment) -> ClassifiedComment:
    """Classify one comment without calling an LLM."""

    text = re.sub(r"\s+", " ", comment.text).strip()
    if _is_noise(text):
        return ClassifiedComment(text, Intent.NOISE, 0.0, comment.timestamp)

    normalized = text.lower()
    matches = [
        intent
        for intent, patterns in _INTENT_PATTERNS.items()
        if any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)
    ]
    intent = max(matches, key=_PRIORITY.get) if matches else Intent.GENERAL
    return ClassifiedComment(text, intent, _PRIORITY[intent], comment.timestamp)


def classify_actionable_comments(
    comments: list[AudienceComment],
) -> list[ClassifiedComment]:
    """Classify comments and remove entries that contain no actionable signal."""

    classified = [classify_comment(comment) for comment in comments]
    return [comment for comment in classified if comment.intent is not Intent.NOISE]
