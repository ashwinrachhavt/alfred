"""add daily_entries and daily_reflections

Creates two new tables backing the Today view:

* ``daily_entries`` — user-captured items (todo | note | learning) keyed by date.
* ``daily_reflections`` — end-of-day digest produced by the reflection pipeline,
  one per day per user (UNIQUE index on ``entry_date``).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i3j4k5l6m7n8"
down_revision: str | Sequence[str] | None = "131d5b9b9bd8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_entries",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_daily_entries_date", "daily_entries", ["entry_date"], unique=False)
    op.create_index(
        "ix_daily_entries_date_kind",
        "daily_entries",
        ["entry_date", "kind"],
        unique=False,
    )
    op.create_index(
        "ix_daily_entries_user_date",
        "daily_entries",
        ["user_id", "entry_date"],
        unique=False,
    )

    op.create_table(
        "daily_reflections",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("digest_md", sa.Text(), nullable=False),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("pipeline_run_id", sa.String(length=64), nullable=False),
        sa.Column("stages_ran", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_daily_reflections_date",
        "daily_reflections",
        ["entry_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_daily_reflections_date", table_name="daily_reflections")
    op.drop_table("daily_reflections")
    op.drop_index("ix_daily_entries_user_date", table_name="daily_entries")
    op.drop_index("ix_daily_entries_date_kind", table_name="daily_entries")
    op.drop_index("ix_daily_entries_date", table_name="daily_entries")
    op.drop_table("daily_entries")
