"""Thread + message persistence for frontend-visible conversations.

This module provides lightweight relational storage for feature outputs that the
frontend can present as "threads" with ordered messages (similar to chat
transcripts). Messages can store both a human-friendly `content` string and a
structured `data` payload (JSONB) for richer UIs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel

from alfred.core.utils import utcnow as _utcnow


class ThreadRow(SQLModel, table=True):
    """Top-level thread record (e.g., an interview-prep session)."""

    __tablename__ = "alfred_threads"
    __table_args__ = (
        sa.Index("ix_alfred_threads_kind", "kind"),
        sa.Index("ix_alfred_threads_updated_at", "updated_at"),
        sa.Index("ix_alfred_threads_user_id", "user_id"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    kind: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    title: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    user_id: int | None = Field(
        default=None,
        sa_column=sa.Column(sa.Integer, sa.ForeignKey("users.id"), nullable=True),
    )
    meta: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=sa.Column(
            "metadata",
            sa.JSON().with_variant(JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


class ThreadMessageRow(SQLModel, table=True):
    """A single message within a thread."""

    __tablename__ = "alfred_thread_messages"
    __table_args__ = (
        sa.Index("ix_alfred_thread_messages_thread_id", "thread_id"),
        sa.Index("ix_alfred_thread_messages_role", "role"),
        sa.Index("ix_alfred_thread_messages_created_at", "created_at"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    thread_id: uuid.UUID = Field(
        sa_column=sa.Column(
            UUID(as_uuid=True),
            sa.ForeignKey("alfred_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    role: str = Field(sa_column=sa.Column(sa.String(length=32), nullable=False))
    content: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=sa.Column(
            sa.JSON().with_variant(JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


__all__ = ["ThreadMessageRow", "ThreadRow"]
