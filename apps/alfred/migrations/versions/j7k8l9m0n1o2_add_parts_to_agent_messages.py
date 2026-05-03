"""add parts to agent_messages

Revision ID: j7k8l9m0n1o2
Revises: f4233855d0d6
Create Date: 2026-05-03 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j7k8l9m0n1o2"
down_revision: str | None = "f4233855d0d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add parts column — canonical AI Elements parts[] store for assistant messages.
    # Nullable so legacy rows (and non-assistant rows) remain valid.
    op.add_column(
        "agent_messages",
        sa.Column("parts", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_messages", "parts")
