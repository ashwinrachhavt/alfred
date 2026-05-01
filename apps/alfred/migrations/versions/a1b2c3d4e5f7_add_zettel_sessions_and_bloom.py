"""add zettel_sessions table and Bloom/enrichment columns on zettel_cards

T1 of the Zettel Creation Workspace plan.

Adds:

* ``zettel_sessions`` — a sitting in which a user creates multiple related
  cards. Status is *derived* (see ``ZettelSession.status``), not stored.
* Six new columns on ``zettel_cards``:
  ``session_id``, ``bloom_level``, ``bloom_source``, ``bloom_history``,
  ``enrichment_attempted_at``, ``enrichment_last_error``.
* Partial indexes: ``session_id IS NOT NULL`` on cards,
  ``ended_at IS NULL`` on sessions (D13).
* CHECK constraints: ``bloom_level BETWEEN 1 AND 6``,
  ``bloom_source IN ('backfill','ai_inferred','user_set','review_updated')``.

Backfill strategy (D2): the two NOT NULL columns (``bloom_level`` and
``bloom_source``) are added nullable first, backfilled deterministically
(``bloom_level=1``, ``bloom_source='backfill'``), and only then altered to
``NOT NULL`` — this avoids the Postgres full-table exclusive lock that a
direct ``ADD COLUMN ... NOT NULL`` would take on a populated table.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: str | Sequence[str] | None = "i3j4k5l6m7n8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------------------------------------------------------------------
    # 1. Create zettel_sessions
    # ---------------------------------------------------------------------
    op.create_table(
        "zettel_sessions",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("shared_topic", sa.String(length=128), nullable=True),
        sa.Column("shared_tags", sa.JSON(), nullable=True),
        sa.Column("source_context", sa.Text(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("card_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary_card_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["summary_card_id"], ["zettel_cards.id"], name="fk_zettel_sessions_summary_card_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_zettel_sessions_active",
        "zettel_sessions",
        ["ended_at"],
        unique=False,
        postgresql_where=sa.text("ended_at IS NULL"),
    )

    # ---------------------------------------------------------------------
    # 2. Add columns on zettel_cards
    # ---------------------------------------------------------------------
    # session_id (nullable FK). We need to know the dialect before adding the
    # constraint: SQLite can't ``ALTER TABLE ADD CONSTRAINT`` (used by
    # alembic's ``create_foreign_key``), so on SQLite we add a bare column
    # and rely on the ORM to enforce the relationship. Postgres (the real
    # deployment target) gets the proper FK constraint.
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    op.add_column(
        "zettel_cards",
        sa.Column("session_id", sa.Integer(), nullable=True),
    )
    if not is_sqlite:
        op.create_foreign_key(
            "fk_zettel_cards_session_id",
            "zettel_cards",
            "zettel_sessions",
            ["session_id"],
            ["id"],
        )

    # bloom_level: add nullable, backfill, then flip to NOT NULL (no exclusive lock).
    op.add_column(
        "zettel_cards",
        sa.Column("bloom_level", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE zettel_cards SET bloom_level = 1 WHERE bloom_level IS NULL")

    # bloom_source: same pattern.
    op.add_column(
        "zettel_cards",
        sa.Column("bloom_source", sa.String(length=32), nullable=True),
    )
    op.execute("UPDATE zettel_cards SET bloom_source = 'backfill' WHERE bloom_source IS NULL")

    # Flip to NOT NULL. SQLite lacks direct ``ALTER COLUMN``, so we only run
    # this on dialects that support it (production is Postgres). The columns
    # remain NOT NULL at the ORM/SQLModel layer regardless.
    if not is_sqlite:
        op.alter_column("zettel_cards", "bloom_level", nullable=False)
        op.alter_column("zettel_cards", "bloom_source", nullable=False)

    # Remaining nullable audit/error columns.
    op.add_column(
        "zettel_cards",
        sa.Column("bloom_history", sa.JSON(), nullable=True),
    )
    op.add_column(
        "zettel_cards",
        sa.Column("enrichment_attempted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "zettel_cards",
        sa.Column("enrichment_last_error", sa.Text(), nullable=True),
    )

    # ---------------------------------------------------------------------
    # 3. CHECK constraints — skipped on SQLite (no ALTER TABLE ADD CHECK).
    # ---------------------------------------------------------------------
    if not is_sqlite:
        op.create_check_constraint(
            "ck_zettel_cards_bloom_level_range",
            "zettel_cards",
            "bloom_level BETWEEN 1 AND 6",
        )
        op.create_check_constraint(
            "ck_zettel_cards_bloom_source_valid",
            "zettel_cards",
            "bloom_source IN ('backfill','ai_inferred','user_set','review_updated')",
        )

    # ---------------------------------------------------------------------
    # 4. Partial index on session_id (D13)
    # ---------------------------------------------------------------------
    op.create_index(
        "ix_zettel_cards_session_id",
        "zettel_cards",
        ["session_id"],
        unique=False,
        postgresql_where=sa.text("session_id IS NOT NULL"),
    )


def downgrade() -> None:
    # Reverse in the opposite order of creation.
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    op.drop_index("ix_zettel_cards_session_id", table_name="zettel_cards")

    if not is_sqlite:
        op.drop_constraint(
            "ck_zettel_cards_bloom_source_valid", "zettel_cards", type_="check"
        )
        op.drop_constraint(
            "ck_zettel_cards_bloom_level_range", "zettel_cards", type_="check"
        )

    op.drop_column("zettel_cards", "enrichment_last_error")
    op.drop_column("zettel_cards", "enrichment_attempted_at")
    op.drop_column("zettel_cards", "bloom_history")
    op.drop_column("zettel_cards", "bloom_source")
    op.drop_column("zettel_cards", "bloom_level")

    if not is_sqlite:
        op.drop_constraint(
            "fk_zettel_cards_session_id", "zettel_cards", type_="foreignkey"
        )
    op.drop_column("zettel_cards", "session_id")

    op.drop_index("ix_zettel_sessions_active", table_name="zettel_sessions")
    op.drop_table("zettel_sessions")
