"""add reasoning_traces to agent_messages

Revision ID: b9c8d7e6f5a4
Revises: f7g8h9i0j1k2, 8dc2b85905aa
Create Date: 2026-03-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9c8d7e6f5a4"
down_revision: tuple[str, ...] = ("f7g8h9i0j1k2", "8dc2b85905aa")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_messages",
        sa.Column("reasoning_traces", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_messages", "reasoning_traces")
