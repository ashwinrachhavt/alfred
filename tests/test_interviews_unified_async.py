from __future__ import annotations

from typing import Any

from alfred.api.interviews_unified import router as interviews_unified_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


class DummyAsyncResult:
    def __init__(self, *, task_id: str) -> None:
        self.id = task_id


class DummyCeleryClient:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send_task(self, name: str, *, kwargs: dict[str, Any], queue: str) -> DummyAsyncResult:  # noqa: ANN401
        self.sent.append({"name": name, "kwargs": kwargs, "queue": queue})
        return DummyAsyncResult(task_id="unified-task-1")


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(interviews_unified_router)
    return TestClient(app)


def test_unified_interview_process_async_enqueues(monkeypatch):
    dummy = DummyCeleryClient()
    monkeypatch.setattr("alfred.api.interviews_unified.routes.get_celery_client", lambda: dummy)

    client = _app()
    resp = client.post(
        "/api/interviews-unified/process?background=true",
        json={"operation": "collect_questions", "company": "Acme", "role": "Software Engineer"},
    )
    assert resp.status_code == 202
    assert resp.json() == {
        "task_id": "unified-task-1",
        "status_url": "/tasks/unified-task-1",
        "status": "queued",
    }

    assert dummy.sent[0]["name"] == "alfred.tasks.interviews_unified.process"
    assert dummy.sent[0]["queue"] == "agent"
    assert dummy.sent[0]["kwargs"]["payload"]["company"] == "Acme"
