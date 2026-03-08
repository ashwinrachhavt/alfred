from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.models.doc_storage import DocumentRow
from alfred.services.doc_storage_pg import DocStorageService


def _make_doc(*, has_image: bool) -> DocumentRow:
    now = datetime.utcnow().replace(tzinfo=UTC)
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
        day_bucket=now.date(),
        captured_at=now,
        captured_hour=now.astimezone(UTC).hour,
        processed_at=now,
        created_at=now,
        updated_at=now,
        image=(b"\x89PNG\r\n\x1a\n" if has_image else None),
        meta={},
    )


def test_list_documents_needing_title_images_filters_on_image() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    doc_missing = _make_doc(has_image=False)
    doc_present = _make_doc(has_image=True)

    with Session(engine) as session:
        session.add(doc_missing)
        session.add(doc_present)
        session.commit()

        svc = DocStorageService(session=session)
        docs = svc.list_documents_needing_title_images(limit=50, min_age_hours=0, force=False)
        ids = {str(d.id) for d in docs}
        assert str(doc_missing.id) in ids
        assert str(doc_present.id) not in ids
