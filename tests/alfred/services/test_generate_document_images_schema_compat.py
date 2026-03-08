from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine, select, text
from sqlmodel import Session, SQLModel

from alfred.models.doc_storage import DocumentRow
from alfred.services.doc_storage_pg import DocStorageService


class _StubLLM:
    def generate_image_png(  # type: ignore[no-untyped-def]
        self, *, prompt: str, model: str, size: str, quality: str
    ):
        _ = prompt, model, size, quality
        return b"\x89PNG\r\n\x1a\nstub", "revised prompt"


def test_generate_document_title_image_does_not_require_concepts_columns() -> None:
    """Ensure image generation works even if optional concepts columns are missing."""

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    now = datetime.utcnow().replace(tzinfo=UTC)
    doc = DocumentRow(
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
        meta={},
        topics={"items": ["testing"]},
        summary={"short": "Short summary", "long": None},
        image=None,
    )
    doc_id = str(doc.id)

    with Session(engine) as session:
        session.add(doc)
        session.commit()

        # Simulate an older database schema where concepts columns do not exist.
        session.execute(text("ALTER TABLE documents DROP COLUMN concepts"))
        session.execute(text("ALTER TABLE documents DROP COLUMN concepts_extracted_at"))
        session.execute(text("ALTER TABLE documents DROP COLUMN concepts_error"))
        session.commit()

        svc = DocStorageService(session=session, llm_service=_StubLLM())
        res = svc.generate_document_title_image(doc_id, force=True)
        assert res["id"] == doc_id
        assert res["skipped"] is False

        row = session.exec(
            select(DocumentRow.image, DocumentRow.meta).where(DocumentRow.id == uuid.UUID(doc_id))
        ).one()
        image, meta = row
        assert image is not None
        assert isinstance(meta, dict)
        assert "generated_cover_image" in meta
