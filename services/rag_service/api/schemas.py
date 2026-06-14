"""Validated HTTP request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CommentInput(BaseModel):
    text: str = Field(min_length=1, max_length=1_000)
    timestamp: str | None = None


class GenerateScriptsRequest(BaseModel):
    comments: list[CommentInput] = Field(min_length=1, max_length=200)
    top_k: int = Field(default=3, ge=1, le=10)
    max_batch_size: int = Field(default=4, ge=1, le=20)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    top_k: int = Field(default=3, ge=1, le=10)


class DocumentResponse(BaseModel):
    tag: str
    text: str
    score: float


class ScriptResponse(BaseModel):
    text: str
    intent: str
    emotion: str
    call_to_action: str
    confidence: float
    source_comments: list[str]
    retrieved_tags: list[str]
    latency_ms: int


class PipelineResponse(BaseModel):
    received_count: int
    filtered_count: int
    generated_count: int
    scripts: list[ScriptResponse]
