"""add agent_messages table and session_type to thinking_sessions

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extend thinking_sessions with agent-specific columns
    op.add_column(
        "thinking_sessions",
        sa.Column("session_type", sa.String(32), nullable=False, server_default="canvas"),
    )
    op.add_column(
        "thinking_sessions",
        sa.Column("active_lens", sa.String(64), nullable=True),
    )
    op.add_column(
        "thinking_sessions",
        sa.Column("model_id", sa.String(128), nullable=True),
    )
    op.create_index("idx_thinking_sessions_type", "thinking_sessions", ["session_type"])

    # Create agent_messages table
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "thread_id",
            sa.Integer,
            sa.ForeignKey("thinking_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("tool_calls", sa.JSON, nullable=True),
        sa.Column("artifacts", sa.JSON, nullable=True),
        sa.Column("related_cards", sa.JSON, nullable=True),
        sa.Column("gaps", sa.JSON, nullable=True),
        sa.Column("active_lens", sa.String(64), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
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

    op.create_index("idx_agent_messages_thread", "agent_messages", ["thread_id"])
    op.create_index(
        "idx_agent_messages_thread_created", "agent_messages", ["thread_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_agent_messages_thread_created", table_name="agent_messages")
    op.drop_index("idx_agent_messages_thread", table_name="agent_messages")
    op.drop_table("agent_messages")

    op.drop_index("idx_thinking_sessions_type", table_name="thinking_sessions")
    op.drop_column("thinking_sessions", "model_id")
    op.drop_column("thinking_sessions", "active_lens")
    op.drop_column("thinking_sessions", "session_type")
