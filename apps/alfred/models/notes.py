"""Postgres-backed note-taking models (Alfred Notes / Atheneum v2).

These tables power hierarchical, markdown-first notes that behave like pages.
They are intentionally separate from the ingestion-focused document storage
tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel

from alfred.core.utils import utcnow as _utcnow


class WorkspaceRow(SQLModel, table=True):
    """A workspace is a top-level container for notes."""

    __tablename__ = "workspaces"
    __table_args__ = (
        sa.Index("ix_workspaces_user_id", "user_id"),
        sa.Index("ix_workspaces_created_at", "created_at"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    name: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    icon: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=10), nullable=True))
    user_id: int | None = Field(
        default=None,
        sa_column=sa.Column(sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    settings: dict[str, Any] = Field(
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


class NoteRow(SQLModel, table=True):
    """A Notion-like page stored as markdown (with optional editor JSON)."""

    __tablename__ = "notes"
    __table_args__ = (
        sa.Index("ix_notes_workspace_parent", "workspace_id", "parent_id"),
        sa.Index("ix_notes_parent_position", "parent_id", "position"),
        sa.Index("ix_notes_updated_at", "updated_at"),
        sa.Index("ix_notes_workspace_archived", "workspace_id", "is_archived"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    title: str = Field(sa_column=sa.Column(sa.String(length=500), nullable=False))
    icon: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=10), nullable=True))
    cover_image: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=500)))
    parent_id: uuid.UUID | None = Field(
        default=None,
        sa_column=sa.Column(
            UUID(as_uuid=True),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    workspace_id: uuid.UUID = Field(
        sa_column=sa.Column(
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    position: int = Field(
        default=0,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    content_markdown: str = Field(
        default="",
        sa_column=sa.Column(sa.Text, nullable=False, server_default=sa.text("''")),
    )
    content_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=sa.Column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=True),
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
    created_by: int | None = Field(
        default=None,
        sa_column=sa.Column(sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    last_edited_by: int | None = Field(
        default=None,
        sa_column=sa.Column(sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    is_archived: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean, nullable=False, server_default=sa.text("false")),
    )


__all__ = ["NoteRow", "WorkspaceRow"]

