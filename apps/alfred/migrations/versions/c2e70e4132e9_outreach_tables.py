"""add outreach run/contact tables

Revision ID: c2e70e4132e9
Revises: d5a9e6d9bead
Create Date: 2025-12-23 15:52:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c2e70e4132e9"
down_revision = "d5a9e6d9bead"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outreach_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_outreach_runs_company", "outreach_runs", ["company"])

    op.create_table(
        "outreach_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("outreach_runs.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), server_default="", nullable=False),
        sa.Column("title", sa.String(length=255), server_default="", nullable=False),
        sa.Column("email", sa.String(length=255), server_default="", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("source", sa.String(length=32), server_default="", nullable=False),
    )
    op.create_index("ix_outreach_contacts_company", "outreach_contacts", ["company"])
    op.create_index("ix_outreach_contacts_email", "outreach_contacts", ["email"])
    op.create_index("ix_outreach_contacts_source", "outreach_contacts", ["source"])
    op.create_index("ix_outreach_contacts_run_id", "outreach_contacts", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_outreach_contacts_run_id", table_name="outreach_contacts")
    op.drop_index("ix_outreach_contacts_source", table_name="outreach_contacts")
    op.drop_index("ix_outreach_contacts_email", table_name="outreach_contacts")
    op.drop_index("ix_outreach_contacts_company", table_name="outreach_contacts")
    op.drop_table("outreach_contacts")
    op.drop_index("ix_outreach_runs_company", table_name="outreach_runs")
    op.drop_table("outreach_runs")
