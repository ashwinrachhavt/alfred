from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.zettels import routes as zettel_routes
from alfred.core.celery_client import BrokerUnavailableError
from alfred.core.exceptions import register_exception_handlers


def _app() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(zettel_routes.router)
    return TestClient(app)


class _FakeDispatch:
    def __init__(self, task_id: str = "task-123", error: Exception | None = None) -> None:
        self.task_id = task_id
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def __call__(self, task_name: str, *, kwargs: dict[str, Any]):
        self.calls.append({"task_name": task_name, "kwargs": kwargs})
        if self.error is not None:
            raise self.error

        class _Result:
            def __init__(self, result_id: str) -> None:
                self.id = result_id

        return _Result(self.task_id)


def test_batch_link_returns_task_id(monkeypatch) -> None:
    fake_dispatch = _FakeDispatch(task_id="batch-1")
    monkeypatch.setattr(zettel_routes, "dispatch_task", fake_dispatch)
    client = _app()

    resp = client.post(
        "/api/zettels/batch-link",
        params={"limit": 25, "max_existing_links": 2, "auto_link": "false"},
    )

    assert resp.status_code == 202
    assert resp.json() == {"task_id": "batch-1"}
    assert fake_dispatch.calls == [
        {
            "task_name": "alfred.tasks.batch_linking.batch_link",
            "kwargs": {"limit": 25, "max_existing_links": 2, "auto_link": False},
        }
    ]


def test_batch_link_returns_503_when_worker_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        zettel_routes,
        "dispatch_task",
        _FakeDispatch(error=BrokerUnavailableError("Background worker unavailable")),
    )
    client = _app()

    resp = client.post("/api/zettels/batch-link")

    assert resp.status_code == 503
    assert resp.json()["error"] == "Background worker unavailable"
    assert resp.json()["code"] == "service_unavailable"
    assert resp.json()["type"] == "ServiceUnavailableError"


def test_generate_links_for_card_returns_503_when_worker_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        zettel_routes,
        "dispatch_task",
        _FakeDispatch(error=BrokerUnavailableError("Background worker unavailable")),
    )
    client = _app()

    resp = client.post("/api/zettels/cards/42/generate-links")

    assert resp.status_code == 503
    assert resp.json()["error"] == "Background worker unavailable"
    assert resp.json()["code"] == "service_unavailable"
    assert resp.json()["type"] == "ServiceUnavailableError"
