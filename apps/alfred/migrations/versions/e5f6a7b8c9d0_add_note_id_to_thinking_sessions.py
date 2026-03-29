"""add note_id to thinking_sessions for notes+AI panel binding

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "thinking_sessions",
        sa.Column("note_id", sa.String(96), nullable=True),
    )
    op.create_index(
        "ix_thinking_sessions_note_id",
        "thinking_sessions",
        ["note_id"],
    )
    op.create_index(
        "uq_thinking_sessions_note_agent",
        "thinking_sessions",
        ["note_id"],
        unique=True,
        postgresql_where=text("session_type = 'agent' AND note_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_thinking_sessions_note_agent", table_name="thinking_sessions")
    op.drop_index("ix_thinking_sessions_note_id", table_name="thinking_sessions")
    op.drop_column("thinking_sessions", "note_id")
