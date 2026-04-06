"""Add performance indexes on zettel_cards.

Adds indexes on status, document_id, and updated_at columns to speed up
filtered list queries and sort operations on the Knowledge Hub.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "h2i3j4k5l6m7"
down_revision: str | tuple[str, ...] | None = "g1h2i3j4k5l6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_zettel_cards_status", "zettel_cards", ["status"], if_not_exists=True)
    op.create_index("ix_zettel_cards_document_id", "zettel_cards", ["document_id"], if_not_exists=True)
    op.create_index("ix_zettel_cards_updated_at", "zettel_cards", ["updated_at"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_zettel_cards_updated_at", table_name="zettel_cards")
    op.drop_index("ix_zettel_cards_document_id", table_name="zettel_cards")
    op.drop_index("ix_zettel_cards_status", table_name="zettel_cards")
