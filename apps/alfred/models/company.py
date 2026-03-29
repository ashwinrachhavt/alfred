"""Research report relational models (Postgres, SQLModel).

Renamed from company_research_reports → research_reports.
This file is kept as company.py for Alembic migration compatibility;
the canonical model now lives here as ``ResearchReportRow``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel

from alfred.core.utils import utcnow as _utcnow


class ResearchReportRow(SQLModel, table=True):
    """Latest generated research report payload (per topic)."""

    __tablename__ = "research_reports"
    __table_args__ = (
        sa.UniqueConstraint("topic_key", name="uq_research_reports_topic_key"),
        sa.Index("ix_research_reports_topic_key", "topic_key"),
        sa.Index("ix_research_reports_updated_at", "updated_at"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    topic_key: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    topic: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    model_name: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    generated_at: datetime | None = Field(
        default=None, sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True)
    )
    payload: dict[str, Any] = Field(
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


# ── Deprecated re-exports for migration / back-compat ──────────────
CompanyResearchReportRow = ResearchReportRow
DeepResearchReportRow = ResearchReportRow

__all__ = ["ResearchReportRow", "CompanyResearchReportRow", "DeepResearchReportRow"]
