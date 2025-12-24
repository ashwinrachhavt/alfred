"""change company_interviews.questions to jsonb

Revision ID: 8b2c9e7c1c9a
Revises: 5c5c5d8a4e3b
Create Date: 2025-12-24
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b2c9e7c1c9a"
down_revision: Union[str, None] = "5c5c5d8a4e3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert text[] -> jsonb for portability and SQLite test support
    op.execute("ALTER TABLE company_interviews ALTER COLUMN questions DROP DEFAULT")
    op.execute(
        "ALTER TABLE company_interviews ALTER COLUMN questions TYPE jsonb USING to_jsonb(questions)"
    )
    op.execute("ALTER TABLE company_interviews ALTER COLUMN questions SET DEFAULT '[]'::jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE company_interviews ALTER COLUMN questions DROP DEFAULT")
    op.execute(
        "ALTER TABLE company_interviews ALTER COLUMN questions TYPE text[] USING ARRAY(SELECT jsonb_array_elements_text(questions))"
    )
    op.execute("ALTER TABLE company_interviews ALTER COLUMN questions SET DEFAULT ARRAY[]::text[]")
