"""add reading_sessions table

Revision ID: 75676ca4c7d0
Revises: 3b5cdc8eb1b6
Create Date: 2026-03-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "75676ca4c7d0"
down_revision: str | None = "3b5cdc8eb1b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reading_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column(
            "engagement_score",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "active_time_ms",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "scroll_depth",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "selection_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "copy_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_revisit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "captured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_reading_sessions_url_hash", "reading_sessions", ["url_hash"])
    op.create_index("ix_reading_sessions_domain", "reading_sessions", ["domain"])
    op.create_index("ix_reading_sessions_created_at", "reading_sessions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_reading_sessions_created_at", table_name="reading_sessions")
    op.drop_index("ix_reading_sessions_domain", table_name="reading_sessions")
    op.drop_index("ix_reading_sessions_url_hash", table_name="reading_sessions")
    op.drop_table("reading_sessions")
