from __future__ import annotations

import uuid
from datetime import date

import sqlalchemy as sa
from alfred.models.doc_storage import DocumentRow
from sqlalchemy import insert
from sqlalchemy.dialects import postgresql, sqlite


def test_document_tags_column_is_text_array() -> None:
    tags_type = DocumentRow.__table__.c.tags.type.load_dialect_impl(postgresql.dialect())
    assert isinstance(tags_type, postgresql.ARRAY)
    assert isinstance(tags_type.item_type, sa.Text)


def test_document_tags_column_is_json_on_sqlite() -> None:
    tags_type = DocumentRow.__table__.c.tags.type.load_dialect_impl(sqlite.dialect())
    assert isinstance(tags_type, sa.JSON)


def test_document_embedding_column_is_float_array() -> None:
    embedding_type = DocumentRow.__table__.c.embedding.type.load_dialect_impl(postgresql.dialect())
    assert isinstance(embedding_type, postgresql.ARRAY)
    assert isinstance(embedding_type.item_type, sa.Float)


def test_document_insert_does_not_cast_tags_to_json() -> None:
    stmt = insert(DocumentRow.__table__).values(
        id=uuid.uuid4(),
        source_url="https://example.com",
        cleaned_text="hello",
        hash="hash",
        day_bucket=date(2025, 12, 26),
        tags=["one", "two"],
    )
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "::JSON" not in compiled
