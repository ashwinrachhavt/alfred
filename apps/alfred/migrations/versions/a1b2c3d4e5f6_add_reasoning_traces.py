"""add reasoning_traces to agent_messages

Revision ID: a1b2c3d4e5f6
Revises: 8dc2b85905aa
Create Date: 2026-03-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "8dc2b85905aa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_messages",
        sa.Column("reasoning_traces", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_messages", "reasoning_traces")
