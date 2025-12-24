"""add outreach_messages table"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b1d3fbd28f9a"
down_revision = "8b2c9e7c1c9a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outreach_messages",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("contact_title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="smtp"),
        sa.Column("provider_message_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )
    op.create_index("ix_outreach_messages_company", "outreach_messages", ["company"])
    op.create_index("ix_outreach_messages_contact_email", "outreach_messages", ["contact_email"])
    op.create_index("ix_outreach_messages_provider", "outreach_messages", ["provider"])
    op.create_index("ix_outreach_messages_status", "outreach_messages", ["status"])


def downgrade() -> None:
    op.drop_index("ix_outreach_messages_status", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_provider", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_contact_email", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_company", table_name="outreach_messages")
    op.drop_table("outreach_messages")
