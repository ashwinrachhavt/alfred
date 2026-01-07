"""add company_research_reports table

Revision ID: 1a9d2f3c4b5e
Revises: 6a1d0c7b9f12
Create Date: 2026-01-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1a9d2f3c4b5e"
down_revision: Union[str, None] = "6a1d0c7b9f12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_research_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("company_key", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("company_key", name="uq_company_research_reports_company_key"),
    )
    op.create_index(
        "ix_company_research_reports_company_key",
        "company_research_reports",
        ["company_key"],
    )
    op.create_index(
        "ix_company_research_reports_updated_at",
        "company_research_reports",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_company_research_reports_updated_at", table_name="company_research_reports")
    op.drop_index("ix_company_research_reports_company_key", table_name="company_research_reports")
    op.drop_table("company_research_reports")
