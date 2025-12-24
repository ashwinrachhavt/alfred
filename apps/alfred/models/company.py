"""Company-related relational models (Postgres, SQLModel)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from alfred.core.utils import utcnow as _utcnow


class CompanyInterviewRow(SQLModel, table=True):
    """Single interview experience (deduped by source_id)."""

    __tablename__ = "company_interviews"
    __table_args__ = (
        sa.Index("ix_company_interviews_company", "company"),
        sa.Index("ix_company_interviews_company_provider", "company", "provider"),
        sa.Index("ix_company_interviews_role", "role"),
        sa.Index("ix_company_interviews_updated_at", "updated_at"),
        sa.UniqueConstraint("source_id", name="uq_company_interviews_source_id"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    company: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    provider: str = Field(sa_column=sa.Column(sa.String(length=32), nullable=False))
    source_id: str = Field(sa_column=sa.Column(sa.String(length=512), nullable=False))
    source_url: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    source_title: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))

    role: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    location: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    interview_date: str | None = Field(
        default=None, sa_column=sa.Column(sa.String(length=64), nullable=True)
    )
    difficulty: str | None = Field(
        default=None, sa_column=sa.Column(sa.String(length=64), nullable=True)
    )
    outcome: str | None = Field(
        default=None, sa_column=sa.Column(sa.String(length=64), nullable=True)
    )

    process_summary: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    questions: list[str] = Field(
        default_factory=list,
        sa_column=sa.Column(sa.JSON, nullable=False, server_default=sa.text("'[]'")),
    )
    raw: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=sa.Column(sa.JSON, nullable=False, server_default=sa.text("'{}'")),
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


__all__ = ["CompanyInterviewRow"]
