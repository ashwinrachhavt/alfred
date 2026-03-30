"""Add index on documents.pipeline_status column.

This index speeds up queries that filter documents by processing status
(pending, processing, complete, error) which is a common pattern in
pipeline monitoring and document processing workflows.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7g8h9i0j1k2"
down_revision: str | tuple[str, ...] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_documents_pipeline_status",
        "documents",
        ["pipeline_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_documents_pipeline_status", table_name="documents")
