"""Validated sales-agent HTTP schemas."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4_000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    fallback_used: bool


class ResetResponse(BaseModel):
    session_id: str
