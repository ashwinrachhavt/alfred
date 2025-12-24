"""add doc storage tables (Postgres-first)

Revision ID: f4c0e2f59d8d
Revises: d5a9e6d9bead
Create Date: 2025-12-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f4c0e2f59d8d"
down_revision: Union[str, None] = "c2e70e4132e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Best-effort: UUID generation helper (available on Postgres)
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # notes
    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
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
    )
    op.create_index("ix_notes_created_at_desc", "notes", ["created_at"])

    # documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(length=64), nullable=False, server_default="web"),
        sa.Column("lang", sa.String(length=24), nullable=True),
        sa.Column("raw_markdown", sa.Text(), nullable=True),
        sa.Column("cleaned_text", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("hash", sa.String(length=128), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("entities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "captured_hour",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("day_bucket", sa.Date(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
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
        sa.Column("session_id", sa.String(length=96), nullable=True),
        sa.Column("agent_run_id", sa.String(length=96), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("enrichment", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "captured_hour >= 0 AND captured_hour <= 23",
            name="ck_documents_captured_hour_bounds",
        ),
    )
    op.create_index("ix_documents_hash", "documents", ["hash"], unique=True)
    op.create_index("ix_documents_captured_at_desc", "documents", ["captured_at"])
    op.create_index("ix_documents_day_bucket", "documents", ["day_bucket"])
    op.create_index(
        "ix_documents_topics", "documents", ["topics"], unique=False, postgresql_using="gin"
    )
    op.create_index(
        "ix_documents_metadata", "documents", ["metadata"], unique=False, postgresql_using="gin"
    )
    op.create_index(
        "ix_documents_tags", "documents", ["tags"], unique=False, postgresql_using="gin"
    )

    # doc_chunks
    op.create_table(
        "doc_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "captured_hour",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("day_bucket", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "captured_hour >= 0 AND captured_hour <= 23",
            name="ck_doc_chunks_captured_hour_bounds",
        ),
    )
    op.create_index("ix_doc_chunks_doc_idx", "doc_chunks", ["doc_id", "idx"], unique=True)
    op.create_index("ix_doc_chunks_captured_at", "doc_chunks", ["captured_at"])
    op.create_index("ix_doc_chunks_day_bucket", "doc_chunks", ["day_bucket"])
    op.create_index(
        "ix_doc_chunks_topics", "doc_chunks", ["topics"], unique=False, postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_doc_chunks_topics", table_name="doc_chunks")
    op.drop_index("ix_doc_chunks_day_bucket", table_name="doc_chunks")
    op.drop_index("ix_doc_chunks_captured_at", table_name="doc_chunks")
    op.drop_index("ix_doc_chunks_doc_idx", table_name="doc_chunks")
    op.drop_table("doc_chunks")

    op.drop_index("ix_documents_tags", table_name="documents")
    op.drop_index("ix_documents_metadata", table_name="documents")
    op.drop_index("ix_documents_topics", table_name="documents")
    op.drop_index("ix_documents_day_bucket", table_name="documents")
    op.drop_index("ix_documents_captured_at_desc", table_name="documents")
    op.drop_index("ix_documents_hash", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_notes_created_at_desc", table_name="notes")
    op.drop_table("notes")
