"""add document image column

Revision ID: 0e3c8f9a1b2d
Revises: 543490e0f01a
Create Date: 2026-01-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0e3c8f9a1b2d"
down_revision: str | None = "543490e0f01a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("image", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "image")
