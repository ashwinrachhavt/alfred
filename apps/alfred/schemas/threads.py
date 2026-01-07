from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ThreadCreate(BaseModel):
    kind: str = Field(..., min_length=1)
    title: str | None = None
    user_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Thread(BaseModel):
    id: str
    kind: str
    title: str | None = None
    user_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ThreadMessageCreate(BaseModel):
    role: str = Field(..., min_length=1)
    content: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ThreadMessage(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


__all__ = [
    "Thread",
    "ThreadCreate",
    "ThreadMessage",
    "ThreadMessageCreate",
]

