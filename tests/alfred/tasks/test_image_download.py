from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from alfred.models.doc_storage import DocumentRow
from alfred.models.document_assets import DocumentAssetRow
from alfred.tasks import image_download


@pytest.fixture()
def db_engine(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    import alfred.core.database as db_mod

    monkeypatch.setattr(db_mod, "SessionLocal", lambda: Session(engine))
    return engine


def _document(raw_markdown: str) -> DocumentRow:
    now = datetime.now(UTC)
    return DocumentRow(
        id=uuid.uuid4(),
        source_url="https://example.com/post",
        canonical_url="https://example.com/post",
        domain="example.com",
        title="Example",
        content_type="web",
        raw_markdown=raw_markdown,
        cleaned_text=raw_markdown,
        tokens=10,
        hash=str(uuid.uuid4()),
        day_bucket=now.date(),
        captured_at=now,
        captured_hour=now.hour,
        processed_at=None,
        created_at=now,
        updated_at=now,
        meta={},
    )


def test_download_document_images_returns_rewrite_map_and_rewrites_markdown(
    db_engine, monkeypatch
) -> None:
    original_url = "https://cdn.example.com/diagram.png"
    doc = _document(f"# Example\n\n![Diagram]({original_url})\n")
    doc_id = doc.id
    with Session(db_engine) as session:
        session.add(doc)
        session.commit()

    def fake_download_one(url: str, alt_text: str) -> dict[str, object]:
        assert url == original_url
        assert alt_text == "Diagram"
        return {
            "original_url": url,
            "alt_text": alt_text,
            "file_name": "diagram.png",
            "mime_type": "image/png",
            "size_bytes": 7,
            "sha256": "abc123",
            "data": b"PNGDATA",
        }

    monkeypatch.setattr(image_download, "_download_one", fake_download_one)

    result = image_download.download_document_images(str(doc_id))

    assert result["status"] == "success"
    assert result["images_downloaded"] == 1
    local_url = result["rewrite_map"][original_url]
    assert local_url.startswith(f"/api/documents/{doc_id}/assets/")

    with Session(db_engine) as session:
        row = session.exec(select(DocumentRow).where(DocumentRow.id == doc_id)).one()
        assets = session.exec(
            select(DocumentAssetRow).where(DocumentAssetRow.doc_id == doc_id)
        ).all()

    assert row.raw_markdown == f"# Example\n\n![Diagram]({local_url})\n"
    assert len(assets) == 1
    assert assets[0].original_url == original_url
    assert assets[0].data == b"PNGDATA"
