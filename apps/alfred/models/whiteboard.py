"""Whiteboard domain models for collaborative diagramming."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String, Text
from sqlmodel import Field

from alfred.models.base import Model


class Whiteboard(Model, table=True):
    """A collaborative canvas with lightweight metadata."""

    __tablename__ = "whiteboards"
    __table_args__ = (
        Index("ix_whiteboards_org_id", "org_id"),
        Index("ix_whiteboards_archived", "is_archived"),
    )

    title: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_by: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    org_id: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    template_id: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    is_archived: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))


class WhiteboardRevision(Model, table=True):
    """Snapshot of a whiteboard scene with optional AI context."""

    __tablename__ = "whiteboard_revisions"
    __table_args__ = (
        Index("ix_whiteboard_revisions_board", "whiteboard_id"),
        Index("ix_whiteboard_revisions_board_rev", "whiteboard_id", "revision_no", unique=True),
    )

    whiteboard_id: int = Field(
        sa_column=Column(Integer, ForeignKey("whiteboards.id"), nullable=False)
    )
    revision_no: int = Field(sa_column=Column(Integer, nullable=False))
    scene_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    ai_context: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    applied_prompt: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_by: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))


class WhiteboardComment(Model, table=True):
    """Threaded comments anchored to whiteboard elements or the canvas."""

    __tablename__ = "whiteboard_comments"
    __table_args__ = (
        Index("ix_whiteboard_comments_board", "whiteboard_id"),
        Index("ix_whiteboard_comments_element", "element_id"),
    )

    whiteboard_id: int = Field(
        sa_column=Column(Integer, ForeignKey("whiteboards.id"), nullable=False)
    )
    element_id: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    body: str = Field(sa_column=Column(Text, nullable=False))
    author: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    resolved: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))


__all__ = ["Whiteboard", "WhiteboardRevision", "WhiteboardComment"]
