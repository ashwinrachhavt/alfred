"""add pipeline_stage_cache table

Revision ID: a1b2c3d4e5f6
Revises: 0e3c8f9a1b2d
Create Date: 2026-03-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "0e3c8f9a1b2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_stage_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("stage", sa.String(), nullable=False, index=True),
        sa.Column("content_hash", sa.String(), nullable=False, index=True),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("stage", "content_hash", name="uq_stage_content_hash"),
    )


def downgrade() -> None:
    op.drop_table("pipeline_stage_cache")
