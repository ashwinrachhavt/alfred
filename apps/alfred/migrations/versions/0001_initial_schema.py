"""Initial database schema for Alfred."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "email_threads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("external_thread_id", sa.String(length=128), nullable=False),
        sa.Column("last_message_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_email_threads_user_external",
        "email_threads",
        ["user_id", "external_thread_id"],
        unique=True,
    )

    op.create_table(
        "prompt_memories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("user_id", "key", name="uq_prompt_memories_user_key"),
    )
    op.create_index("ix_prompt_memories_key", "prompt_memories", ["key"], unique=False)

    op.create_table(
        "email_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "thread_id",
            sa.Integer(),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "google_credentials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_key", sa.String(length=64), nullable=False),
        sa.Column("credential", sa.JSON(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("is_calendar", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_google_credentials_user", "google_credentials", ["user_key"], unique=False)
    op.create_index(
        "ix_google_credentials_user_calendar",
        "google_credentials",
        ["user_key", "is_calendar"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_google_credentials_user_calendar", table_name="google_credentials")
    op.drop_index("ix_google_credentials_user", table_name="google_credentials")
    op.drop_table("google_credentials")

    op.drop_table("email_actions")

    op.drop_index("ix_prompt_memories_key", table_name="prompt_memories")
    op.drop_table("prompt_memories")

    op.drop_index("ix_email_threads_user_external", table_name="email_threads")
    op.drop_index("ix_email_threads_thread_id", table_name="email_threads")
    op.drop_table("email_threads")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
