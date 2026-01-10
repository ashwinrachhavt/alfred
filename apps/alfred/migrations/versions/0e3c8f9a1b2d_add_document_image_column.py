"""add document image column

Revision ID: 0e3c8f9a1b2d
Revises: 543490e0f01a
Create Date: 2026-01-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0e3c8f9a1b2d"
down_revision: Union[str, None] = "543490e0f01a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("image", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "image")
