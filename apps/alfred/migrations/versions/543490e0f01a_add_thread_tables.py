"""add thread tables

Revision ID: 543490e0f01a
Revises: 1a9d2f3c4b5e
Create Date: 2026-01-07 00:16:03.244611

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "543490e0f01a"
down_revision: Union[str, None] = "1a9d2f3c4b5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alfred_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_alfred_threads_kind", "alfred_threads", ["kind"])
    op.create_index("ix_alfred_threads_updated_at", "alfred_threads", ["updated_at"])
    op.create_index("ix_alfred_threads_user_id", "alfred_threads", ["user_id"])

    op.create_table(
        "alfred_thread_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alfred_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_alfred_thread_messages_thread_id",
        "alfred_thread_messages",
        ["thread_id"],
    )
    op.create_index("ix_alfred_thread_messages_role", "alfred_thread_messages", ["role"])
    op.create_index(
        "ix_alfred_thread_messages_created_at",
        "alfred_thread_messages",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_alfred_thread_messages_created_at",
        table_name="alfred_thread_messages",
    )
    op.drop_index("ix_alfred_thread_messages_role", table_name="alfred_thread_messages")
    op.drop_index(
        "ix_alfred_thread_messages_thread_id",
        table_name="alfred_thread_messages",
    )
    op.drop_table("alfred_thread_messages")

    op.drop_index("ix_alfred_threads_user_id", table_name="alfred_threads")
    op.drop_index("ix_alfred_threads_updated_at", table_name="alfred_threads")
    op.drop_index("ix_alfred_threads_kind", table_name="alfred_threads")
    op.drop_table("alfred_threads")
