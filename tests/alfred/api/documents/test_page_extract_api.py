from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.documents import routes as doc_routes
from alfred.core.celery_client import BrokerUnavailableError
from alfred.core.exceptions import register_exception_handlers


class _FakeDocStorage:
    def __init__(self) -> None:
        self._next_id = 1
        self.last_ingest: dict[str, Any] | None = None
        self.last_ingest_kwargs: dict[str, Any] | None = None
        self.duplicate_next = False

    def ingest_document_store_only(self, ingest, **kwargs: Any) -> dict[str, Any]:
        self.last_ingest = {
            "source_url": ingest.source_url,
            "title": ingest.title,
            "cleaned_text": ingest.cleaned_text,
            "raw_markdown": ingest.raw_markdown,
            "content_type": ingest.content_type,
            "metadata": ingest.metadata,
        }
        self.last_ingest_kwargs = kwargs
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
            "selection_type": "selection",
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


def test_full_page_http_capture_always_queues_coordinator(monkeypatch) -> None:
    fake = _FakeDocStorage()
    client = _app_with_fake_service(fake)
    calls: list[dict[str, Any]] = []

    def fake_dispatch(task_name: str, *, kwargs: dict[str, Any]) -> object:
        calls.append({"task_name": task_name, "kwargs": kwargs})
        return object()

    monkeypatch.setattr(doc_routes, "dispatch_task", fake_dispatch)

    resp = client.post(
        "/api/documents/page/extract",
        json={
            "raw_text": "x" * 80,
            "page_url": "https://www.edge.ceo/p/the-smile-curve-has-come-for-software",
            "page_title": "The Smile Curve Has Come for Software",
            "selection_type": "full_page",
            "capture_quality": "basic",
        },
    )

    assert resp.status_code == 201
    assert resp.json()["status"] == "accepted"
    assert fake.last_ingest_kwargs == {"skip_pipeline": True}
    assert fake.last_ingest is not None
    assert fake.last_ingest["metadata"] == {
        "capture": {
            "source": "chrome_extension",
            "mode": "full_page",
            "rich_capture_status": "queued",
            "local_quality": "basic",
        }
    }
    assert calls == [
        {
            "task_name": "alfred.tasks.capture_coordinator.coordinate_capture",
            "kwargs": {
                "doc_id": "1",
                "source_url": "https://www.edge.ceo/p/the-smile-curve-has-come-for-software",
                "has_images": False,
                "content_type_hint": "generic",
                "force_firecrawl": True,
            },
        }
    ]


def test_selection_capture_does_not_force_coordinator(monkeypatch) -> None:
    fake = _FakeDocStorage()
    client = _app_with_fake_service(fake)
    calls: list[dict[str, Any]] = []

    def fake_dispatch(task_name: str, *, kwargs: dict[str, Any]) -> object:
        calls.append({"task_name": task_name, "kwargs": kwargs})
        return object()

    monkeypatch.setattr(doc_routes, "dispatch_task", fake_dispatch)

    resp = client.post(
        "/api/documents/page/extract",
        json={
            "raw_text": "Selected text " * 8,
            "raw_markdown": "**Selected text**",
            "page_url": "https://example.com/post",
            "page_title": "Example",
            "selection_type": "selection",
            "content_type_hint": "article",
            "capture_quality": "rich",
        },
    )

    assert resp.status_code == 201
    assert resp.json()["status"] == "accepted"
    assert fake.last_ingest_kwargs == {"skip_pipeline": False}
    assert fake.last_ingest is not None
    assert fake.last_ingest["metadata"] == {"content_type_hint": "article"}
    assert calls == []


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


def test_page_extract_returns_accepted_when_queue_dispatch_fails(monkeypatch) -> None:
    fake = _FakeDocStorage()
    client = _app_with_fake_service(fake)
    calls: list[dict[str, Any]] = []

    def fake_dispatch(task_name: str, *, kwargs: dict[str, Any]) -> None:
        calls.append({"task_name": task_name, "kwargs": kwargs})
        raise BrokerUnavailableError("Background worker unavailable")

    monkeypatch.setattr(doc_routes, "dispatch_task", fake_dispatch)

    resp = client.post(
        "/api/documents/page/extract",
        json={
            "raw_text": "x" * 60,
            "raw_markdown": "# Example\n\nBody",
            "page_url": "https://example.com/post",
            "page_title": "Example",
        },
    )

    assert resp.status_code == 201
    assert resp.json() == {"id": "1", "status": "accepted", "task_id": None, "status_url": None}
    assert fake.last_ingest_kwargs == {"skip_pipeline": True}
    assert calls == [
        {
            "task_name": "alfred.tasks.capture_coordinator.coordinate_capture",
            "kwargs": {
                "doc_id": "1",
                "source_url": "https://example.com/post",
                "has_images": False,
                "content_type_hint": "generic",
                "force_firecrawl": True,
            },
        },
        {
            "task_name": "alfred.tasks.document_pipeline.run_document_pipeline",
            "kwargs": {"doc_id": "1"},
        },
    ]


def test_page_extract_rejects_empty_cleaned_content() -> None:
    fake = _FakeDocStorage()
    client = _app_with_fake_service(fake)

    cookie_wall = ("We use cookies to improve your experience.\n" * 10).strip()

    resp = client.post(
        "/api/documents/page/extract",
        json={
            "raw_text": cookie_wall,
            "page_url": "https://example.com",
            "selection_type": "full_page",
        },
    )

    assert resp.status_code == 422
    assert resp.json()["error"] == "No extractable text found in page content."
    assert fake.last_ingest is None


def test_enqueue_document_enrichment(monkeypatch) -> None:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(doc_routes.router)
    client = TestClient(app)

    class _FakeAsyncResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id

    calls: list[dict[str, Any]] = []

    def fake_dispatch(task_name: str, *, kwargs: dict[str, Any]) -> _FakeAsyncResult:
        calls.append({"task_name": task_name, "kwargs": kwargs})
        return _FakeAsyncResult("task-123")

    monkeypatch.setattr(doc_routes, "dispatch_task", fake_dispatch)

    resp = client.post("/api/documents/doc/abc/enrich", params={"force": "true"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "abc"
    assert data["status"] == "queued"
    assert data["task_id"] == "task-123"
    assert data["status_url"] == "/tasks/task-123"
    assert calls == [
        {
            "task_name": "alfred.tasks.document_enrichment.enrich",
            "kwargs": {"doc_id": "abc", "force": True},
        }
    ]


def test_enqueue_document_enrichment_returns_503_when_worker_is_unavailable(monkeypatch) -> None:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(doc_routes.router)
    client = TestClient(app)
    monkeypatch.setattr(
        doc_routes,
        "dispatch_task",
        lambda task_name, *, kwargs: (_ for _ in ()).throw(
            BrokerUnavailableError("Background worker unavailable")
        ),
    )

    resp = client.post("/api/documents/doc/abc/enrich")

    assert resp.status_code == 503
    assert resp.json()["error"] == "Background worker unavailable"
    assert resp.json()["code"] == "service_unavailable"
    assert resp.json()["type"] == "ServiceUnavailableError"
