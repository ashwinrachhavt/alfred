"""Pydantic schemas for the Thinking Canvas feature."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ThinkingBlock(BaseModel):
    """A single block in a thinking session."""

    id: str  # uuid v4
    type: str  # freeform|demolition|framework|anchor|law|prediction|connection|insight
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)
    order: int = 0


class ThinkingSessionCreate(BaseModel):
    title: str | None = None
    topic: str | None = None
    source_input: dict | None = None
    blocks: list[ThinkingBlock] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ThinkingSessionUpdate(BaseModel):
    title: str | None = None
    blocks: list[ThinkingBlock] | None = None
    tags: list[str] | None = None
    topic: str | None = None
    pinned: bool | None = None
    status: str | None = None  # for archive/restore


class ThinkingSessionResponse(BaseModel):
    id: int
    title: str | None
    status: str
    blocks: list[ThinkingBlock]
    tags: list[str]
    topic: str | None
    source_input: dict | None
    pinned: bool
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class ThinkingSessionSummary(BaseModel):
    id: int
    title: str | None
    status: str
    topic: str | None
    pinned: bool
    tags: list[str]
    block_count: int
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class DecomposeRequest(BaseModel):
    input_type: str  # topic | url | text
    content: str


class DecomposeResponse(BaseModel):
    blocks: list[ThinkingBlock]


__all__ = [
    "ThinkingBlock",
    "ThinkingSessionCreate",
    "ThinkingSessionUpdate",
    "ThinkingSessionResponse",
    "ThinkingSessionSummary",
    "DecomposeRequest",
    "DecomposeResponse",
]
