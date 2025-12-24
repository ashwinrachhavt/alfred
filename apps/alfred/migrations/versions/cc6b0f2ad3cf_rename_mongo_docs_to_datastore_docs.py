"""rename mongo_docs to datastore_docs"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "cc6b0f2ad3cf"
down_revision = "b1d3fbd28f9a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("mongo_docs", "datastore_docs")
    op.execute(
        "ALTER INDEX IF EXISTS ix_mongo_docs_collection RENAME TO ix_datastore_docs_collection"
    )
    op.execute("ALTER INDEX IF EXISTS ix_mongo_docs_data_gin RENAME TO ix_datastore_docs_data_gin")
    op.execute(
        "ALTER INDEX IF EXISTS uq_mongo_docs_collection_doc_id RENAME TO uq_datastore_docs_collection_doc_id"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX IF EXISTS uq_datastore_docs_collection_doc_id RENAME TO uq_mongo_docs_collection_doc_id"
    )
    op.execute("ALTER INDEX IF EXISTS ix_datastore_docs_data_gin RENAME TO ix_mongo_docs_data_gin")
    op.execute(
        "ALTER INDEX IF EXISTS ix_datastore_docs_collection RENAME TO ix_mongo_docs_collection"
    )
    op.rename_table("datastore_docs", "mongo_docs")
