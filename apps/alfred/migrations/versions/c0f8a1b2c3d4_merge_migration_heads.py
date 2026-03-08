"""merge migration heads

Revision ID: c0f8a1b2c3d4
Revises: 0e3c8f9a1b2d, 1d7b9c3d1e21
Create Date: 2026-01-08
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0f8a1b2c3d4"
down_revision: str | tuple[str, ...] | None = ("0e3c8f9a1b2d", "1d7b9c3d1e21")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Merge revision; no schema changes.
    op.execute("SELECT 1")


def downgrade() -> None:
    # Merge revision; no schema changes.
    op.execute("SELECT 1")
