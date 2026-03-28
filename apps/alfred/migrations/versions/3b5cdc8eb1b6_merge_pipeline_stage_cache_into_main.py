"""merge pipeline_stage_cache into main

Revision ID: 3b5cdc8eb1b6
Revises: 3b8f2a7c1d4e, a1b2c3d4e5f6
Create Date: 2026-03-20 18:24:45.897291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b5cdc8eb1b6'
down_revision: Union[str, None] = ('3b8f2a7c1d4e', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
