"""merge_all_heads

Revision ID: 131d5b9b9bd8
Revises: aeb74f6161e4, e6f7a8b9c0d1, h2i3j4k5l6m7
Create Date: 2026-04-10 19:31:32.076537

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '131d5b9b9bd8'
down_revision: Union[str, None] = ('aeb74f6161e4', 'e6f7a8b9c0d1', 'h2i3j4k5l6m7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
