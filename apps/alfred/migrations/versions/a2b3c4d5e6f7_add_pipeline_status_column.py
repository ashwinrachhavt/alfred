"""add pipeline_status column to documents

Revision ID: a2b3c4d5e6f7
Revises: 75676ca4c7d0
Create Date: 2026-03-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "75676ca4c7d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "pipeline_status",
            sa.String(length=24),
            nullable=False,
            server_default=sa.text("'complete'"),
        ),
    )
    # Allow processed_at to be NULL for pending documents
    op.alter_column("documents", "processed_at", nullable=True)


def downgrade() -> None:
    op.alter_column("documents", "processed_at", nullable=False)
    op.drop_column("documents", "pipeline_status")
