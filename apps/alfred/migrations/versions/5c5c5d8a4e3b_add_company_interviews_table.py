"""add company_interviews table

Revision ID: 5c5c5d8a4e3b
Revises: 0cf3e4bf3c4c
Create Date: 2025-12-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5c5c5d8a4e3b"
down_revision: Union[str, None] = "0cf3e4bf3c4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_interviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=512), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_title", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("interview_date", sa.String(length=64), nullable=True),
        sa.Column("difficulty", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=64), nullable=True),
        sa.Column("process_summary", sa.Text(), nullable=True),
        sa.Column(
            "questions",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column(
            "raw",
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
        sa.UniqueConstraint("source_id", name="uq_company_interviews_source_id"),
    )
    op.create_index("ix_company_interviews_company", "company_interviews", ["company"])
    op.create_index(
        "ix_company_interviews_company_provider",
        "company_interviews",
        ["company", "provider"],
    )
    op.create_index("ix_company_interviews_role", "company_interviews", ["role"])
    op.create_index("ix_company_interviews_updated_at", "company_interviews", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_company_interviews_updated_at", table_name="company_interviews")
    op.drop_index("ix_company_interviews_role", table_name="company_interviews")
    op.drop_index("ix_company_interviews_company_provider", table_name="company_interviews")
    op.drop_index("ix_company_interviews_company", table_name="company_interviews")
    op.drop_table("company_interviews")
