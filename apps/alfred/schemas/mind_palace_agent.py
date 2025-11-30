from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str


class AgentQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    history: List[ChatMessage] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    answer: str
    sources: Optional[List[Dict[str, Any]]] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "ChatMessage",
    "AgentQueryRequest",
    "AgentResponse",
]
