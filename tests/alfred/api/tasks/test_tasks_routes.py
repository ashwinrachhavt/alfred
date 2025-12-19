from __future__ import annotations

from typing import Any

from alfred.api.tasks import router as tasks_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


class DummyAsyncResult:
    def __init__(
        self,
        *,
        task_id: str,
        status: str = "PENDING",
        ready: bool = False,
        successful: bool = False,
        failed: bool = False,
        result: Any = None,
    ) -> None:
        self.id = task_id
        self.status = status
        self.result = result
        self._ready = ready
        self._successful = successful
        self._failed = failed

    def ready(self) -> bool:
        return self._ready

    def successful(self) -> bool:
        return self._successful

    def failed(self) -> bool:
        return self._failed


class DummyCeleryClient:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.results: dict[str, DummyAsyncResult] = {}

    def send_task(self, name: str, *, kwargs: dict[str, Any], queue: str) -> DummyAsyncResult:  # noqa: ANN401
        self.sent.append({"name": name, "kwargs": kwargs, "queue": queue})
        result = DummyAsyncResult(task_id="task-123")
        self.results[result.id] = result
        return result

    def AsyncResult(self, task_id: str) -> DummyAsyncResult:  # noqa: N802
        return self.results.get(task_id, DummyAsyncResult(task_id=task_id))


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(tasks_router)
    return app


def test_get_task_status_includes_result(monkeypatch):
    dummy = DummyCeleryClient()
    dummy.results["task-1"] = DummyAsyncResult(
        task_id="task-1",
        status="SUCCESS",
        ready=True,
        successful=True,
        result="hello",
    )
    monkeypatch.setattr("alfred.api.tasks.routes.get_celery_client", lambda: dummy)

    client = TestClient(create_app())
    resp = client.get("/tasks/task-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["result"] == "hello"


def test_get_task_status_excludes_result(monkeypatch):
    dummy = DummyCeleryClient()
    dummy.results["task-2"] = DummyAsyncResult(
        task_id="task-2",
        status="SUCCESS",
        ready=True,
        successful=True,
        result="hello",
    )
    monkeypatch.setattr("alfred.api.tasks.routes.get_celery_client", lambda: dummy)

    client = TestClient(create_app())
    resp = client.get("/tasks/task-2?include_result=false")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["result"] is None


def test_llm_chat_task_endpoint_removed():
    client = TestClient(create_app())
    resp = client.post(
        "/tasks/llm/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 404
