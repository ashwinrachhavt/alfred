from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.documents import routes as doc_routes
from alfred.core.exceptions import register_exception_handlers


class _FakeDocStorage:
    def __init__(self) -> None:
        self._next_id = 1
        self.last_ingest: dict[str, Any] | None = None
        self.duplicate_next = False

    def ingest_document_store_only(self, ingest, **kwargs: Any) -> dict[str, Any]:
        self.last_ingest = {
            "source_url": ingest.source_url,
            "title": ingest.title,
            "cleaned_text": ingest.cleaned_text,
            "content_type": ingest.content_type,
        }
        if self.duplicate_next:
            return {"id": "dup-id", "duplicate": True}
        doc_id = str(self._next_id)
        self._next_id += 1
        return {"id": doc_id, "duplicate": False}


def _app_with_fake_service(fake: _FakeDocStorage) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(doc_routes.router)
    app.dependency_overrides[doc_routes.get_doc_storage_service] = lambda: fake
    return TestClient(app)


def test_page_extract_stores_only(monkeypatch) -> None:
    """Verify page/extract saves instantly and returns 201 without dispatching
    a redundant Celery task (the service layer already dispatches the pipeline).
    """
    fake = _FakeDocStorage()
    client = _app_with_fake_service(fake)

    resp = client.post(
        "/api/documents/page/extract",
        json={
            "raw_text": "x" * 60,
            "page_url": "https://example.com",
            "page_title": "Example",
            "selection_type": "full_page",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["id"] == "1"

    assert fake.last_ingest is not None
    assert fake.last_ingest["source_url"] == "https://example.com"
    assert fake.last_ingest["title"] == "Example"
    assert fake.last_ingest["content_type"] == "web"


def test_page_extract_duplicate_short_circuits() -> None:
    fake = _FakeDocStorage()
    fake.duplicate_next = True
    client = _app_with_fake_service(fake)

    resp = client.post(
        "/api/documents/page/extract",
        json={"raw_text": "x" * 60, "page_url": "https://example.com"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "duplicate"
    assert data["id"] == "dup-id"


def test_enqueue_document_enrichment(monkeypatch) -> None:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(doc_routes.router)
    client = TestClient(app)

    class _FakeAsyncResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id

    class _FakeCelery:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def send_task(self, name: str, *, kwargs: dict[str, Any]) -> _FakeAsyncResult:
            self.calls.append({"name": name, "kwargs": kwargs})
            return _FakeAsyncResult("task-123")

    fake_celery = _FakeCelery()
    monkeypatch.setattr(doc_routes, "get_celery_client", lambda: fake_celery)

    resp = client.post("/api/documents/doc/abc/enrich", params={"force": "true"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "abc"
    assert data["status"] == "queued"
    assert data["task_id"] == "task-123"
    assert data["status_url"] == "/tasks/task-123"
    assert fake_celery.calls == [
        {
            "name": "alfred.tasks.document_enrichment.enrich",
            "kwargs": {"doc_id": "abc", "force": True},
        }
    ]
