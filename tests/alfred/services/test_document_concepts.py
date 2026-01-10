from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from alfred.models.doc_storage import DocumentRow
from alfred.services.doc_storage_pg import DocStorageService
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class _StubExtractor:
    def extract_graph(self, *, text: str, metadata: dict | None = None):  # type: ignore[no-untyped-def]
        _ = text, metadata
        return {
            "entities": [{"name": "Redis", "type": "technology"}],
            "relations": [{"from": "Redis", "to": "Cache", "type": "USED_FOR"}],
            "topics": ["caching"],
        }


def _make_doc(*, created_at: datetime, extracted: bool) -> DocumentRow:
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    return DocumentRow(
        id=uuid.uuid4(),
        source_url="https://example.com",
        canonical_url="https://example.com",
        domain="example.com",
        title="Example",
        content_type="web",
        cleaned_text="hello world",
        tokens=2,
        hash=str(uuid.uuid4()),
        day_bucket=created_at.date(),
        captured_at=created_at,
        captured_hour=created_at.astimezone(timezone.utc).hour,
        processed_at=now,
        created_at=created_at,
        updated_at=now,
        concepts_extracted_at=(now if extracted else None),
        concepts={"entities": []} if extracted else None,
        concepts_error=None,
    )


def test_list_documents_needing_concepts_extraction_filters_extracted(db_session: Session) -> None:
    older = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(hours=10)
    doc_pending = _make_doc(created_at=older, extracted=False)
    doc_done = _make_doc(created_at=older, extracted=True)
    db_session.add(doc_pending)
    db_session.add(doc_done)
    db_session.commit()

    svc = DocStorageService(session=db_session)
    docs = svc.list_documents_needing_concepts_extraction(limit=50, min_age_hours=0, force=False)
    ids = {str(d.id) for d in docs}
    assert str(doc_pending.id) in ids
    assert str(doc_done.id) not in ids


def test_extract_document_concepts_persists_payload(db_session: Session) -> None:
    older = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(hours=1)
    doc = _make_doc(created_at=older, extracted=False)
    db_session.add(doc)
    db_session.commit()

    svc = DocStorageService(session=db_session, extraction_service=_StubExtractor())
    res = svc.extract_document_concepts(str(doc.id), force=False)
    assert res["id"] == str(doc.id)
    assert res["skipped"] is False
    assert res["entities"] == 1
    assert res["relations"] == 1

    refreshed = db_session.get(DocumentRow, doc.id)
    assert refreshed is not None
    assert refreshed.concepts_extracted_at is not None
    assert refreshed.concepts_error is None
    assert (refreshed.concepts or {}).get("topics") == ["caching"]
