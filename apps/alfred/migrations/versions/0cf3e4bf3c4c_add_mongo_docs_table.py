"""add generic mongo_docs table

Revision ID: 0cf3e4bf3c4c
Revises: f4c0e2f59d8d
Create Date: 2025-12-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0cf3e4bf3c4c"
down_revision: Union[str, None] = "f4c0e2f59d8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mongo_docs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("collection", sa.Text(), nullable=False),
        sa.Column("doc_id", sa.String(length=96), nullable=False),
        sa.Column(
            "data",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("collection", "doc_id", name="uq_mongo_docs_collection_doc_id"),
    )
    op.create_index("ix_mongo_docs_collection", "mongo_docs", ["collection"])
    op.create_index(
        "ix_mongo_docs_data_gin", "mongo_docs", ["data"], unique=False, postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_mongo_docs_data_gin", table_name="mongo_docs")
    op.drop_index("ix_mongo_docs_collection", table_name="mongo_docs")
    op.drop_table("mongo_docs")
