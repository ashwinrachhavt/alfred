from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WhiteboardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    created_by: str | None = Field(default=None, max_length=255)
    org_id: str | None = Field(default=None, max_length=128)
    template_id: str | None = Field(default=None, max_length=128)
    initial_scene: dict[str, Any] | None = None
    ai_context: dict[str, Any] | None = None
    applied_prompt: str | None = Field(default=None, max_length=2048)


class WhiteboardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    template_id: str | None = Field(default=None, max_length=128)
    is_archived: bool | None = None


class WhiteboardOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    created_by: str | None = None
    org_id: str | None = None
    template_id: str | None = None
    is_archived: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class WhiteboardRevisionCreate(BaseModel):
    scene_json: dict[str, Any] = Field(default_factory=dict)
    ai_context: dict[str, Any] | None = None
    applied_prompt: str | None = Field(default=None, max_length=2048)
    created_by: str | None = Field(default=None, max_length=255)


class WhiteboardRevisionOut(BaseModel):
    id: int
    whiteboard_id: int
    revision_no: int
    scene_json: dict[str, Any]
    ai_context: dict[str, Any] | None = None
    applied_prompt: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class WhiteboardCommentCreate(BaseModel):
    body: str = Field(min_length=1)
    element_id: str | None = Field(default=None, max_length=128)
    author: str | None = Field(default=None, max_length=255)


class WhiteboardCommentOut(BaseModel):
    id: int
    whiteboard_id: int
    element_id: str | None = None
    body: str
    author: str | None = None
    resolved: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class WhiteboardWithRevision(WhiteboardOut):
    latest_revision: WhiteboardRevisionOut | None = None
