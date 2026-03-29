"""rename company_research_reports → research_reports, company_key → topic_key, company → topic

Revision ID: a8f3b2c1d4e5
Revises: 75676ca4c7d0
Create Date: 2026-03-28
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8f3b2c1d4e5"
down_revision: str | None = "75676ca4c7d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Rename columns first (while table still has old name)
    op.alter_column("company_research_reports", "company_key", new_column_name="topic_key")
    op.alter_column("company_research_reports", "company", new_column_name="topic")

    # Drop old indexes and constraints (they reference old names)
    op.drop_index("ix_company_research_reports_company_key", table_name="company_research_reports")
    op.drop_index("ix_company_research_reports_updated_at", table_name="company_research_reports")
    op.drop_constraint("uq_company_research_reports_company_key", table_name="company_research_reports", type_="unique")

    # Rename the table
    op.rename_table("company_research_reports", "research_reports")

    # Recreate indexes and constraints with new names
    op.create_unique_constraint("uq_research_reports_topic_key", "research_reports", ["topic_key"])
    op.create_index("ix_research_reports_topic_key", "research_reports", ["topic_key"])
    op.create_index("ix_research_reports_updated_at", "research_reports", ["updated_at"])


def downgrade() -> None:
    # Drop new indexes and constraints
    op.drop_index("ix_research_reports_updated_at", table_name="research_reports")
    op.drop_index("ix_research_reports_topic_key", table_name="research_reports")
    op.drop_constraint("uq_research_reports_topic_key", table_name="research_reports", type_="unique")

    # Rename table back
    op.rename_table("research_reports", "company_research_reports")

    # Rename columns back
    op.alter_column("company_research_reports", "topic_key", new_column_name="company_key")
    op.alter_column("company_research_reports", "topic", new_column_name="company")

    # Recreate old indexes and constraints
    op.create_unique_constraint("uq_company_research_reports_company_key", "company_research_reports", ["company_key"])
    op.create_index("ix_company_research_reports_company_key", "company_research_reports", ["company_key"])
    op.create_index("ix_company_research_reports_updated_at", "company_research_reports", ["updated_at"])
