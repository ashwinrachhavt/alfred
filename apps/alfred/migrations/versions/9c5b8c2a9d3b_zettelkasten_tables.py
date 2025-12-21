"""zettelkasten tables

Revision ID: 9c5b8c2a9d3b
Revises: 7b6cf0a0d4c4
Create Date: 2025-12-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c5b8c2a9d3b"
down_revision: Union[str, None] = "7b6cf0a0d4c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zettel_cards",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("topic", sa.String(length=128), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("document_id", sa.String(length=96), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_zettel_cards_topic", "zettel_cards", ["topic"], unique=False)
    op.create_index("ix_zettel_cards_title", "zettel_cards", ["title"], unique=False)

    op.create_table(
        "zettel_links",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_card_id", sa.Integer(), nullable=False),
        sa.Column("to_card_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("bidirectional", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["from_card_id"], ["zettel_cards.id"]),
        sa.ForeignKeyConstraint(["to_card_id"], ["zettel_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_zettel_links_from", "zettel_links", ["from_card_id"], unique=False)
    op.create_index("ix_zettel_links_to", "zettel_links", ["to_card_id"], unique=False)
    op.create_index(
        "ix_zettel_links_unique",
        "zettel_links",
        ["from_card_id", "to_card_id", "type"],
        unique=True,
    )

    op.create_table(
        "zettel_reviews",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["card_id"], ["zettel_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_zettel_reviews_card_id", "zettel_reviews", ["card_id"], unique=False)
    op.create_index("ix_zettel_reviews_due_at", "zettel_reviews", ["due_at"], unique=False)
    op.create_index(
        "ix_zettel_reviews_open_due",
        "zettel_reviews",
        ["completed_at", "due_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_zettel_reviews_open_due", table_name="zettel_reviews")
    op.drop_index("ix_zettel_reviews_due_at", table_name="zettel_reviews")
    op.drop_index("ix_zettel_reviews_card_id", table_name="zettel_reviews")
    op.drop_table("zettel_reviews")
    op.drop_index("ix_zettel_links_unique", table_name="zettel_links")
    op.drop_index("ix_zettel_links_to", table_name="zettel_links")
    op.drop_index("ix_zettel_links_from", table_name="zettel_links")
    op.drop_table("zettel_links")
    op.drop_index("ix_zettel_cards_title", table_name="zettel_cards")
    op.drop_index("ix_zettel_cards_topic", table_name="zettel_cards")
    op.drop_table("zettel_cards")
