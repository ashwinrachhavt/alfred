"""add wiki_links table for note/zettel → card wiki-links

Revision ID: aeb74f6161e4
Revises: b9c8d7e6f5a4
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "aeb74f6161e4"
down_revision: str = "b9c8d7e6f5a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wiki_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("target_card_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["target_card_id"], ["zettel_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wiki_links_source", "wiki_links", ["source_type", "source_id"])
    op.create_index("ix_wiki_links_target", "wiki_links", ["target_card_id"])
    op.create_index(
        "ix_wiki_links_unique",
        "wiki_links",
        ["source_type", "source_id", "target_card_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_wiki_links_unique", table_name="wiki_links")
    op.drop_index("ix_wiki_links_target", table_name="wiki_links")
    op.drop_index("ix_wiki_links_source", table_name="wiki_links")
    op.drop_table("wiki_links")
