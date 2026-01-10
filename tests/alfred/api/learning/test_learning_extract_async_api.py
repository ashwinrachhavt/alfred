from __future__ import annotations

from typing import Any, Dict

from alfred.api.learning import routes as learning_routes
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(learning_routes.router)
    return TestClient(app)


def test_enqueue_learning_resource_extraction(monkeypatch) -> None:
    client = _app()

    class _FakeAsyncResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id

    class _FakeCelery:
        def __init__(self) -> None:
            self.calls: list[Dict[str, Any]] = []

        def send_task(self, name: str, *, kwargs: Dict[str, Any]) -> _FakeAsyncResult:
            self.calls.append({"name": name, "kwargs": kwargs})
            return _FakeAsyncResult("task-123")

    fake_celery = _FakeCelery()
    monkeypatch.setattr(learning_routes, "get_celery_client", lambda: fake_celery)

    resp = client.post("/api/learning/resources/42/extract/async", params={"force": "true"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["task_id"] == "task-123"
    assert data["status_url"] == "/tasks/task-123"
    assert data["resource_id"] == 42
    assert fake_celery.calls == [
        {
            "name": "alfred.tasks.learning_concepts.extract_resource",
            "kwargs": {"resource_id": 42, "force": True},
        }
    ]


def test_enqueue_learning_batch_extraction(monkeypatch) -> None:
    client = _app()

    class _FakeAsyncResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id

    class _FakeCelery:
        def __init__(self) -> None:
            self.calls: list[Dict[str, Any]] = []

        def send_task(self, name: str, *, kwargs: Dict[str, Any]) -> _FakeAsyncResult:
            self.calls.append({"name": name, "kwargs": kwargs})
            return _FakeAsyncResult("task-999")

    fake_celery = _FakeCelery()
    monkeypatch.setattr(learning_routes, "get_celery_client", lambda: fake_celery)

    resp = client.post(
        "/api/learning/resources/extract/batch/async",
        json={"limit": 25, "topic_id": 7, "min_age_hours": 6, "force": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["task_id"] == "task-999"
    assert data["status_url"] == "/tasks/task-999"
    assert fake_celery.calls == [
        {
            "name": "alfred.tasks.learning_concepts.batch_extract",
            "kwargs": {
                "limit": 25,
                "topic_id": 7,
                "min_age_hours": 6,
                "force": False,
                "enqueue_only": True,
            },
        }
    ]
