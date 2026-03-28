"""Reading session tracking models.

Stores engagement data for pages the user reads, enabling reading history,
analytics, and automatic capture of high-engagement content.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from alfred.core.utils import utcnow as _utcnow


class ReadingSessionRow(SQLModel, table=True):
    """One row per tracked page reading event."""

    __tablename__ = "reading_sessions"
    __table_args__ = (
        sa.Index("ix_reading_sessions_url_hash", "url_hash"),
        sa.Index("ix_reading_sessions_domain", "domain"),
        sa.Index("ix_reading_sessions_created_at", "created_at"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    url: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    url_hash: str = Field(
        sa_column=sa.Column(sa.String(length=64), nullable=False),
    )
    title: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    domain: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    engagement_score: int = Field(
        default=0,
        sa_column=sa.Column(sa.SmallInteger, nullable=False, server_default=sa.text("0")),
    )
    active_time_ms: int = Field(
        default=0,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    scroll_depth: int = Field(
        default=0,
        sa_column=sa.Column(sa.SmallInteger, nullable=False, server_default=sa.text("0")),
    )
    selection_count: int = Field(
        default=0,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    copy_count: int = Field(
        default=0,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    is_revisit: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    captured: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    document_id: uuid.UUID | None = Field(
        default=None,
        sa_column=sa.Column(
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    @staticmethod
    def hash_url(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()


__all__ = ["ReadingSessionRow"]
