"""add generic source context to agent threads

Revision ID: l9m0n1o2p3q4
Revises: k8l9m0n1o2p3
Create Date: 2026-05-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "l9m0n1o2p3q4"
down_revision = "k8l9m0n1o2p3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("thinking_sessions", sa.Column("source_kind", sa.String(length=32), nullable=True))
    op.add_column("thinking_sessions", sa.Column("source_id", sa.String(length=96), nullable=True))
    op.create_index(
        "idx_thinking_sessions_source",
        "thinking_sessions",
        ["source_kind", "source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_thinking_sessions_source", table_name="thinking_sessions")
    op.drop_column("thinking_sessions", "source_id")
    op.drop_column("thinking_sessions", "source_kind")
