"""add taxonomy framework tables and seed domains

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create taxonomy_nodes table
    op.create_table(
        "taxonomy_nodes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=128), unique=True, nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("level", sa.SmallInteger, nullable=False),
        sa.Column(
            "parent_slug",
            sa.String(length=128),
            sa.ForeignKey("taxonomy_nodes.slug", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_taxonomy_nodes_level", "taxonomy_nodes", ["level"])
    op.create_index("ix_taxonomy_nodes_parent_slug", "taxonomy_nodes", ["parent_slug"])

    # 2. Seed 11 initial domains
    op.bulk_insert(
        sa.table(
            "taxonomy_nodes",
            sa.column("slug", sa.String),
            sa.column("display_name", sa.String),
            sa.column("level", sa.SmallInteger),
            sa.column("parent_slug", sa.String),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {
                "slug": "system-design",
                "display_name": "System Design",
                "level": 1,
                "parent_slug": None,
                "sort_order": 1,
            },
            {
                "slug": "ai-engineering",
                "display_name": "AI Engineering",
                "level": 1,
                "parent_slug": None,
                "sort_order": 2,
            },
            {
                "slug": "finance",
                "display_name": "Finance",
                "level": 1,
                "parent_slug": None,
                "sort_order": 3,
            },
            {
                "slug": "startups",
                "display_name": "Startups",
                "level": 1,
                "parent_slug": None,
                "sort_order": 4,
            },
            {
                "slug": "investments",
                "display_name": "Investments",
                "level": 1,
                "parent_slug": None,
                "sort_order": 5,
            },
            {
                "slug": "writing-literature",
                "display_name": "Writing & Literature",
                "level": 1,
                "parent_slug": None,
                "sort_order": 6,
            },
            {
                "slug": "politics-geopolitics",
                "display_name": "Politics & Geopolitics",
                "level": 1,
                "parent_slug": None,
                "sort_order": 7,
            },
            {
                "slug": "philosophy",
                "display_name": "Philosophy",
                "level": 1,
                "parent_slug": None,
                "sort_order": 8,
            },
            {
                "slug": "movies-pop-culture",
                "display_name": "Movies & Pop Culture",
                "level": 1,
                "parent_slug": None,
                "sort_order": 9,
            },
            {
                "slug": "productivity-career",
                "display_name": "Productivity & Career",
                "level": 1,
                "parent_slug": None,
                "sort_order": 10,
            },
            {
                "slug": "general",
                "display_name": "General",
                "level": 1,
                "parent_slug": None,
                "sort_order": 99,
            },
        ],
    )

    # 3. Add classification column to documents table
    op.add_column(
        "documents",
        sa.Column("classification", sa.JSON, nullable=True),
    )
    op.create_index(
        "ix_documents_classification_domain",
        "documents",
        [sa.text("(classification->>'domain')")],
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("ix_documents_classification_domain", table_name="documents")
    op.drop_column("documents", "classification")

    op.drop_index("ix_taxonomy_nodes_parent_slug", table_name="taxonomy_nodes")
    op.drop_index("ix_taxonomy_nodes_level", table_name="taxonomy_nodes")
    op.drop_table("taxonomy_nodes")
