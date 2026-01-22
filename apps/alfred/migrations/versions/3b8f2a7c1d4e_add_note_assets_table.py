"""Add note assets table.

Revision ID: 3b8f2a7c1d4e
Revises: 2d0e971dd90b, 2f4c8a1d9b7e
Create Date: 2026-01-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3b8f2a7c1d4e"
down_revision: Union[str, tuple[str, ...], None] = ("2d0e971dd90b", "2f4c8a1d9b7e")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "note_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "note_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=200), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
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
    )
    op.create_index("ix_note_assets_note_id", "note_assets", ["note_id"])
    op.create_index("ix_note_assets_workspace_id", "note_assets", ["workspace_id"])
    op.create_index("ix_note_assets_created_at", "note_assets", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_note_assets_created_at", table_name="note_assets")
    op.drop_index("ix_note_assets_workspace_id", table_name="note_assets")
    op.drop_index("ix_note_assets_note_id", table_name="note_assets")
    op.drop_table("note_assets")

