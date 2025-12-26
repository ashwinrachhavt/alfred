from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from sqlalchemy import insert
from sqlalchemy.dialects import postgresql

from alfred.models.doc_storage import DocumentRow


def test_document_tags_column_is_text_array() -> None:
    tags_type = DocumentRow.__table__.c.tags.type
    assert isinstance(tags_type, postgresql.ARRAY)
    assert isinstance(tags_type.item_type, sa.Text)


def test_document_insert_does_not_cast_tags_to_json() -> None:
    stmt = insert(DocumentRow.__table__).values(
        source_url="https://example.com",
        cleaned_text="hello",
        hash="hash",
        day_bucket=date(2025, 12, 26),
        tags=["one", "two"],
    )
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "::JSON" not in compiled
