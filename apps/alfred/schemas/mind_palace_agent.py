from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str


class AgentQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

__all__ = [
    "ChatMessage",
    "AgentQueryRequest",
    "AgentResponse",
]
