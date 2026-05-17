from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from alfred.models.doc_storage import DocumentRow
from alfred.models.document_assets import (
    DocumentAssetRow,  # noqa: F401 - ensure table is registered
)
from alfred.tasks import capture_coordinator


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


def _document(**overrides) -> DocumentRow:
    now = datetime.now(UTC)
    data = {
        "id": uuid.uuid4(),
        "source_url": "https://www.edge.ceo/p/the-smile-curve-has-come-for-software",
        "canonical_url": "https://www.edge.ceo/p/the-smile-curve-has-come-for-software",
        "domain": "edge.ceo",
        "title": "Extension Title",
        "content_type": "web",
        "raw_markdown": "# Extension Title\n\nBasic page body.",
        "cleaned_text": "Extension Title\n\nBasic page body.",
        "tokens": 5,
        "hash": str(uuid.uuid4()),
        "day_bucket": now.date(),
        "captured_at": now,
        "captured_hour": now.hour,
        "processed_at": None,
        "created_at": now,
        "updated_at": now,
        "meta": {
            "capture": {
                "source": "chrome_extension",
                "mode": "full_page",
                "rich_capture_status": "queued",
                "local_quality": "basic",
            }
        },
    }
    data.update(overrides)
    return DocumentRow(**data)


def test_coordinate_capture_force_firecrawl_updates_source_capture_then_dispatches_pipeline(
    db_engine, monkeypatch
) -> None:
    doc = _document()
    doc_id = doc.id
    source_url = doc.source_url
    with Session(db_engine) as session:
        session.add(doc)
        session.commit()

    scrape_calls: list[str] = []

    class FakeFirecrawlClient:
        def scrape_rich(self, url: str, *, render_js: bool = False):
            scrape_calls.append(f"{url}|{render_js}")
            return SimpleNamespace(
                success=True,
                markdown=(
                    "# The Smile Curve Has Come for Software\n\n"
                    "Software value is moving.\n\n"
                    "![Smile curve](https://cdn.example.com/smile.png)\n\n"
                    "## The old bundle\n\n"
                    "Distribution and services are changing."
                ),
                html="<article><h1>The Smile Curve Has Come for Software</h1></article>",
                metadata={
                    "title": "The Smile Curve Has Come for Software",
                    "description": "Why software value capture is shifting.",
                    "author": "Edge Staff",
                    "publishedTime": "2026-05-01T00:00:00Z",
                    "ogImage": "https://cdn.example.com/cover.png",
                    "og:type": "article",
                },
            )

    pipeline_calls: list[dict[str, str]] = []
    image_calls: list[str] = []

    def fake_download(doc_id: str) -> dict[str, object]:
        image_calls.append(doc_id)
        return {
            "status": "success",
            "images_downloaded": 1,
            "rewrite_map": {
                "https://cdn.example.com/smile.png": f"/api/documents/{doc_id}/assets/asset-1"
            },
        }

    class FakePipeline:
        @staticmethod
        def delay(**kwargs):
            pipeline_calls.append(kwargs)

    monkeypatch.setattr(capture_coordinator, "FirecrawlClient", FakeFirecrawlClient, raising=False)
    monkeypatch.setattr(
        "alfred.tasks.image_download.download_document_images",
        fake_download,
    )
    monkeypatch.setattr(
        "alfred.tasks.document_pipeline.run_document_pipeline",
        FakePipeline,
    )

    result = capture_coordinator.coordinate_capture(
        doc_id=str(doc_id),
        source_url=source_url,
        has_images=False,
        content_type_hint="generic",
        force_firecrawl=True,
        user_id="user-1",
    )

    assert result["steps_completed"] == ["firecrawl", "image_download", "pipeline_dispatch"]
    assert result["firecrawl"] == "upgraded"
    assert scrape_calls == [f"{source_url}|False"]
    assert image_calls == [str(doc_id)]
    assert pipeline_calls == [{"doc_id": str(doc_id), "user_id": "user-1"}]

    with Session(db_engine) as session:
        row = session.exec(select(DocumentRow).where(DocumentRow.id == doc_id)).one()

    assert row.title == "The Smile Curve Has Come for Software"
    assert row.raw_markdown.startswith("# The Smile Curve Has Come for Software")
    assert row.cleaned_text.startswith("# The Smile Curve Has Come for Software")
    assert row.meta["capture"]["rich_capture_status"] == "complete"
    source_capture = row.meta["source_capture"]
    assert source_capture["kind"] == "blog_article"
    assert source_capture["platform"] == "substack"
    assert source_capture["author"] == "Edge Staff"
    assert source_capture["images"][0]["url"] == "https://cdn.example.com/smile.png"
    assert source_capture["images"][0]["local_url"] == f"/api/documents/{doc_id}/assets/asset-1"


def test_coordinate_capture_applies_image_rewrite_map_to_source_capture(
    db_engine, monkeypatch
) -> None:
    doc = _document(
        raw_markdown=(
            "# Captured Page\n\n"
            "![Diagram](https://cdn.example.com/diagram.png)\n\n"
            "Body text."
        ),
        meta={
            "source_capture": {
                "kind": "blog_article",
                "images": [
                    {
                        "url": "https://cdn.example.com/diagram.png",
                        "alt": "Diagram",
                        "position": 0,
                    }
                ],
                "cover_image_url": "https://cdn.example.com/diagram.png",
            },
            "capture": {"rich_capture_status": "complete"},
        },
    )
    doc_id = doc.id
    source_url = doc.source_url
    with Session(db_engine) as session:
        session.add(doc)
        session.commit()

    image_calls: list[str] = []

    def fake_download(doc_id: str) -> dict[str, object]:
        image_calls.append(doc_id)
        return {
            "status": "success",
            "images_downloaded": 1,
            "rewrite_map": {
                "https://cdn.example.com/diagram.png": f"/api/documents/{doc_id}/assets/asset-1"
            },
        }

    pipeline_calls: list[dict[str, str]] = []

    class FakePipeline:
        @staticmethod
        def delay(**kwargs):
            pipeline_calls.append(kwargs)

    monkeypatch.setattr(
        "alfred.tasks.image_download.download_document_images",
        fake_download,
    )
    monkeypatch.setattr(
        "alfred.tasks.document_pipeline.run_document_pipeline",
        FakePipeline,
    )

    result = capture_coordinator.coordinate_capture(
        doc_id=str(doc_id),
        source_url=source_url,
        has_images=True,
        content_type_hint="article",
    )

    assert result["steps_completed"] == ["image_download", "pipeline_dispatch"]
    assert image_calls == [str(doc_id)]
    assert pipeline_calls == [{"doc_id": str(doc_id), "user_id": ""}]

    with Session(db_engine) as session:
        row = session.exec(select(DocumentRow).where(DocumentRow.id == doc_id)).one()

    image = row.meta["source_capture"]["images"][0]
    assert image["local_url"] == f"/api/documents/{doc_id}/assets/asset-1"
    assert row.meta["source_capture"]["cover_image_url"] == f"/api/documents/{doc_id}/assets/asset-1"
