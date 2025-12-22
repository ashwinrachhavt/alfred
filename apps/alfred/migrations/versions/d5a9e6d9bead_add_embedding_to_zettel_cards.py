"""add embedding column to zettel_cards

Revision ID: d5a9e6d9bead
Revises: 9c5b8c2a9d3b
Create Date: 2025-12-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5a9e6d9bead"
down_revision: Union[str, None] = "9c5b8c2a9d3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("zettel_cards", sa.Column("embedding", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("zettel_cards", "embedding")
