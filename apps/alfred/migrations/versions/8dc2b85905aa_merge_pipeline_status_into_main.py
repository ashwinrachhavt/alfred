"""merge pipeline_status into main

Revision ID: 8dc2b85905aa
Revises: a2b3c4d5e6f7, e5f6a7b8c9d0
Create Date: 2026-03-29 14:01:06.624782

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '8dc2b85905aa'
down_revision: str | None = ('a2b3c4d5e6f7', 'e5f6a7b8c9d0')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
