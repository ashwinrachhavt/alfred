"""Add document_assets table for storing downloaded page images.

Revision ID: g1h2i3j4k5l6
Revises: f7g8h9i0j1k2
Create Date: 2026-04-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "g1h2i3j4k5l6"
down_revision = "f7g8h9i0j1k2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "doc_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=200), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_document_assets_doc_id", "document_assets", ["doc_id"])
    op.create_index("ix_document_assets_created_at", "document_assets", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_document_assets_created_at", table_name="document_assets")
    op.drop_index("ix_document_assets_doc_id", table_name="document_assets")
    op.drop_table("document_assets")
