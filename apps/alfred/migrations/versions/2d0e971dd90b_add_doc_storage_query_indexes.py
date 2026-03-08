"""Add indexes to speed up doc storage explorer/search queries.

These indexes focus on high-traffic read paths:
- Explorer cursor pagination (`created_at DESC, id DESC`)
- Semantic map refresh (`updated_at DESC`)
- Primary topic filtering (`topics ->> 'primary'`)
- Backlog scans for title images and concept extraction (partial indexes)
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "2d0e971dd90b"
down_revision: str | tuple[str, ...] | None = "c0f8a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Postgres-only indexes (JSONB ops, partial indexes with predicates).
    if context.get_context().dialect.name != "postgresql":
        return

    # Explorer cursor pagination and general recency ordering.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_created_at_id_desc "
        "ON documents (created_at DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_updated_at_desc " "ON documents (updated_at DESC)"
    )

    # Topic filters use: documents.topics['primary'].astext == <topic>
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_topics_primary "
        "ON documents ((topics->>'primary'))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_doc_chunks_topics_primary "
        "ON doc_chunks ((topics->>'primary'))"
    )

    # Backlog scans (partial indexes).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_title_image_backlog "
        "ON documents (created_at DESC, id DESC) "
        "WHERE image IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_concepts_backlog "
        "ON documents (created_at ASC, id ASC) "
        "WHERE concepts_extracted_at IS NULL"
    )

    # Common access pattern for document chunk lists: filter by doc_id, order by captured_at DESC.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_doc_chunks_doc_id_captured_at_desc "
        "ON doc_chunks (doc_id, captured_at DESC)"
    )


def downgrade() -> None:
    if context.get_context().dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_doc_chunks_doc_id_captured_at_desc")
    op.execute("DROP INDEX IF EXISTS ix_documents_concepts_backlog")
    op.execute("DROP INDEX IF EXISTS ix_documents_title_image_backlog")
    op.execute("DROP INDEX IF EXISTS ix_doc_chunks_topics_primary")
    op.execute("DROP INDEX IF EXISTS ix_documents_topics_primary")
    op.execute("DROP INDEX IF EXISTS ix_documents_updated_at_desc")
    op.execute("DROP INDEX IF EXISTS ix_documents_created_at_id_desc")
