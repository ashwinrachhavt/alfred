"""add vocabulary_entries table

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-04-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vocabulary_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False, server_default=sa.text("'en'")),
        sa.Column("pronunciation_ipa", sa.String(length=512), nullable=True),
        sa.Column("pronunciation_audio_url", sa.String(length=2048), nullable=True),
        sa.Column("definitions", sa.JSON, nullable=True),
        sa.Column("etymology", sa.Text, nullable=True),
        sa.Column("synonyms", sa.JSON, nullable=True),
        sa.Column("antonyms", sa.JSON, nullable=True),
        sa.Column("usage_notes", sa.Text, nullable=True),
        sa.Column("wikipedia_summary", sa.Text, nullable=True),
        sa.Column("ai_explanation", sa.Text, nullable=True),
        sa.Column("ai_explanation_domains", sa.JSON, nullable=True),
        sa.Column("source_urls", sa.JSON, nullable=True),
        sa.Column("personal_notes", sa.Text, nullable=True),
        sa.Column("domain_tags", sa.JSON, nullable=True),
        sa.Column("save_intent", sa.String(length=32), nullable=False, server_default=sa.text("'learning'")),
        sa.Column("bloom_level", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "zettel_id",
            sa.Integer,
            sa.ForeignKey("zettel_cards.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_vocabulary_entries_word", "vocabulary_entries", ["word"])
    op.create_index("ix_vocabulary_entries_user_id", "vocabulary_entries", ["user_id"])
    op.create_index("ix_vocabulary_entries_save_intent", "vocabulary_entries", ["save_intent"])


def downgrade() -> None:
    op.drop_index("ix_vocabulary_entries_save_intent", table_name="vocabulary_entries")
    op.drop_index("ix_vocabulary_entries_user_id", table_name="vocabulary_entries")
    op.drop_index("ix_vocabulary_entries_word", table_name="vocabulary_entries")
    op.drop_table("vocabulary_entries")
