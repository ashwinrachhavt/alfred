"""add Alfred Notes tables

Revision ID: 2f4c8a1d9b7e
Revises: c0f8a1b2c3d4
Create Date: 2026-01-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2f4c8a1d9b7e"
down_revision: str | None = "c0f8a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Rename legacy quick-capture notes table to free up `notes` for Alfred Notes pages.
    op.rename_table("notes", "quick_notes")
    op.drop_index("ix_notes_created_at_desc", table_name="quick_notes")
    op.create_index("ix_quick_notes_created_at_desc", "quick_notes", ["created_at"])

    # Workspaces (container for notes hierarchy)
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("icon", sa.String(length=10), nullable=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "settings",
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
    op.create_index("ix_workspaces_user_id", "workspaces", ["user_id"])
    op.create_index("ix_workspaces_created_at", "workspaces", ["created_at"])

    # Notes (pages)
    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("icon", sa.String(length=10), nullable=True),
        sa.Column("cover_image", sa.String(length=500), nullable=True),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "content_markdown",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "last_edited_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_notes_workspace_parent", "notes", ["workspace_id", "parent_id"])
    op.create_index("ix_notes_parent_position", "notes", ["parent_id", "position"])
    op.create_index("ix_notes_updated_at", "notes", ["updated_at"])
    op.create_index("ix_notes_workspace_archived", "notes", ["workspace_id", "is_archived"])


def downgrade() -> None:
    op.drop_index("ix_notes_workspace_archived", table_name="notes")
    op.drop_index("ix_notes_updated_at", table_name="notes")
    op.drop_index("ix_notes_parent_position", table_name="notes")
    op.drop_index("ix_notes_workspace_parent", table_name="notes")
    op.drop_table("notes")

    op.drop_index("ix_workspaces_created_at", table_name="workspaces")
    op.drop_index("ix_workspaces_user_id", table_name="workspaces")
    op.drop_table("workspaces")

    op.drop_index("ix_quick_notes_created_at_desc", table_name="quick_notes")
    op.create_index("ix_notes_created_at_desc", "quick_notes", ["created_at"])
    op.rename_table("quick_notes", "notes")
