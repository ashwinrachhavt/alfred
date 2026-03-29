"""add thinking_sessions table

Revision ID: b2c3d4e5f6a7
Revises: a8f3b2c1d4e5
Create Date: 2026-03-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a8f3b2c1d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "thinking_sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("blocks", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("tags", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("topic", sa.Text, nullable=True),
        sa.Column("source_input", sa.JSON, nullable=True),
        sa.Column("pinned", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("idx_thinking_sessions_status", "thinking_sessions", ["status"])
    op.create_index("idx_thinking_sessions_updated", "thinking_sessions", ["updated_at"])


def downgrade() -> None:
    op.drop_index("idx_thinking_sessions_updated", table_name="thinking_sessions")
    op.drop_index("idx_thinking_sessions_status", table_name="thinking_sessions")
    op.drop_table("thinking_sessions")
