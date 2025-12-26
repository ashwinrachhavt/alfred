"""Postgres-backed relational models for document/notes storage.

These mirror the Mongo doc storage collections but use strongly typed
columns and indexes optimised for Postgres.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlmodel import Field, SQLModel

from alfred.core.utils import utcnow as _utcnow


class NoteRow(SQLModel, table=True):
    """Lightweight note record."""

    __tablename__ = "notes"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    text: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    source_url: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    meta: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=sa.Column(
            "metadata",
            sa.JSON,
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


class DocumentRow(SQLModel, table=True):
    """Primary document table (metadata + text + enrichment)."""

    __tablename__ = "documents"
    __table_args__ = (
        sa.Index("ix_documents_hash", "hash", unique=True),
        sa.Index("ix_documents_captured_at_desc", "captured_at"),
        sa.Index("ix_documents_day_bucket", "day_bucket"),
        sa.Index("ix_documents_topics", "topics", postgresql_using="gin"),
        sa.Index("ix_documents_metadata", "metadata", postgresql_using="gin"),
        sa.Index("ix_documents_tags", "tags", postgresql_using="gin"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    source_url: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    canonical_url: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    domain: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    title: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    content_type: str = Field(
        default="web", sa_column=sa.Column(sa.String(length=64), nullable=False)
    )
    lang: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=24), nullable=True))
    raw_markdown: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    cleaned_text: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    tokens: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, nullable=True))
    hash: str = Field(sa_column=sa.Column(sa.String(length=128), nullable=False))
    summary: dict[str, Any] | None = Field(
        default=None, sa_column=sa.Column(sa.JSON, nullable=True)
    )
    topics: dict[str, Any] | None = Field(default=None, sa_column=sa.Column(sa.JSON, nullable=True))
    entities: dict[str, Any] | None = Field(
        default=None, sa_column=sa.Column(sa.JSON, nullable=True)
    )
    tags: list[str] = Field(
        default_factory=list,
        sa_column=sa.Column(
            ARRAY(sa.Text),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
    )
    embedding: list[float] | None = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )
    captured_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    captured_hour: int = Field(
        default=0,
        sa_column=sa.Column(
            sa.SmallInteger,
            nullable=False,
            server_default=sa.text("0"),
            info={"check": "captured_hour between 0 and 23"},
        ),
    )
    day_bucket: date = Field(sa_column=sa.Column(sa.Date, nullable=False))
    published_at: datetime | None = Field(
        default=None, sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True)
    )
    processed_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
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
    session_id: str | None = Field(default=None, sa_column=sa.Column(sa.String(96), nullable=True))
    agent_run_id: str | None = Field(
        default=None, sa_column=sa.Column(sa.String(96), nullable=True)
    )
    meta: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=sa.Column(
            "metadata",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    enrichment: dict[str, Any] | None = Field(
        default=None, sa_column=sa.Column(sa.JSON, nullable=True)
    )


class DocChunkRow(SQLModel, table=True):
    """Chunk table linking back to documents."""

    __tablename__ = "doc_chunks"
    __table_args__ = (
        sa.Index("ix_doc_chunks_doc_idx", "doc_id", "idx", unique=True),
        sa.Index("ix_doc_chunks_captured_at", "captured_at"),
        sa.Index("ix_doc_chunks_day_bucket", "day_bucket"),
        sa.Index("ix_doc_chunks_topics", "topics", postgresql_using="gin"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    doc_id: uuid.UUID = Field(
        sa_column=sa.Column(
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    idx: int = Field(sa_column=sa.Column(sa.Integer, nullable=False))
    text: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    tokens: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, nullable=True))
    section: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    char_start: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, nullable=True))
    char_end: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, nullable=True))
    embedding: list[float] | None = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )
    topics: dict[str, Any] | None = Field(default=None, sa_column=sa.Column(sa.JSON, nullable=True))
    captured_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    captured_hour: int = Field(
        default=0,
        sa_column=sa.Column(
            sa.SmallInteger,
            nullable=False,
            server_default=sa.text("0"),
            info={"check": "captured_hour between 0 and 23"},
        ),
    )
    day_bucket: date = Field(sa_column=sa.Column(sa.Date, nullable=False))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


__all__ = ["NoteRow", "DocumentRow", "DocChunkRow"]
