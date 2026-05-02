"""add run_id and projected_from_events to agent_messages

Revision ID: f4233855d0d6
Revises: s0t1r2e3a4m5
Create Date: 2026-05-01 18:10:28.168155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4233855d0d6'
down_revision: Union[str, None] = 's0t1r2e3a4m5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add run_id column to link messages to streaming agent_runs
    op.add_column(
        "agent_messages",
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_agent_messages_run_id",
        "agent_messages", "agent_runs",
        ["run_id"], ["id"],
        ondelete="SET NULL"
    )
    op.create_index("idx_agent_messages_run_id", "agent_messages", ["run_id"])

    # Add projected_from_events flag to distinguish v2 rows from v1
    op.add_column(
        "agent_messages",
        sa.Column("projected_from_events", sa.Boolean(), nullable=False, server_default="false")
    )


def downgrade() -> None:
    op.drop_column("agent_messages", "projected_from_events")
    op.drop_index("idx_agent_messages_run_id", table_name="agent_messages")
    op.drop_constraint("fk_agent_messages_run_id", "agent_messages", type_="foreignkey")
    op.drop_column("agent_messages", "run_id")
