from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.interviews_unified import router as interviews_unified_router


class DummyAsyncResult:
    def __init__(self, *, task_id: str) -> None:
        self.id = task_id


class DummyCeleryClient:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send_task(self, name: str, *args: Any, **options: Any) -> DummyAsyncResult:
        kwargs = options.get("kwargs") or {}
        queue = options.get("queue")
        task_id = options.get("task_id") or "unified-task-1"
        self.sent.append({"name": name, "kwargs": kwargs, "queue": queue, "task_id": task_id})
        return DummyAsyncResult(task_id=str(task_id))


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(interviews_unified_router)
    return TestClient(app)


def test_unified_interview_process_async_enqueues(monkeypatch):
    dummy = DummyCeleryClient()
    monkeypatch.setattr("alfred.api.interviews_unified.routes.get_celery_client", lambda: dummy)
    monkeypatch.setattr(
        "alfred.api.interviews_unified.routes.uuid.uuid4",
        lambda: uuid.UUID(int=1),
    )

    client = _app()
    resp = client.post(
        "/api/interviews-unified/process?background=true",
        json={"operation": "collect_questions", "company": "Acme", "role": "Software Engineer"},
    )

    task_id = str(uuid.UUID(int=1))
    assert resp.status_code == 202
    assert resp.json() == {
        "task_id": task_id,
        "status_url": f"/tasks/{task_id}",
        "status": "queued",
    }

    assert dummy.sent[0]["name"] == "alfred.tasks.interviews_unified.process"
    assert dummy.sent[0]["queue"] == "agent"
    assert dummy.sent[0]["task_id"] == task_id
    assert dummy.sent[0]["kwargs"]["payload"]["company"] == "Acme"
