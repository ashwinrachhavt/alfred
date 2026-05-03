"""merge streaming + zettel_sessions heads

Revision ID: 19c5c333743f
Revises: a1b2c3d4e5f7, f4233855d0d6
Create Date: 2026-05-02 05:25:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "19c5c333743f"
down_revision: str | Sequence[str] | None = ("a1b2c3d4e5f7", "f4233855d0d6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
