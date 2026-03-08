"""add document concept extraction columns

Revision ID: 1d7b9c3d1e21
Revises: 6a1d0c7b9f12
Create Date: 2026-01-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1d7b9c3d1e21"
down_revision: str | None = "6a1d0c7b9f12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("concepts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("concepts_extracted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("concepts_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "concepts_error")
    op.drop_column("documents", "concepts_extracted_at")
    op.drop_column("documents", "concepts")
