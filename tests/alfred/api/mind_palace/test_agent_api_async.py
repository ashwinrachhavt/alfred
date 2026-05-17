from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.mind_palace_agent import routes as mp_agent_routes


class DummyAsyncResult:
    def __init__(self, *, task_id: str) -> None:
        self.id = task_id


class DummyTaskDispatcher:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def __call__(self, name: str, *, kwargs: dict[str, Any], queue: str) -> DummyAsyncResult:
        self.sent.append({"name": name, "kwargs": kwargs, "queue": queue})
        return DummyAsyncResult(task_id="agent-task-1")


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(mp_agent_routes.router)
    return TestClient(app)


def test_agent_query_async_enqueues(monkeypatch):
    dummy = DummyTaskDispatcher()
    monkeypatch.setattr("alfred.api.mind_palace_agent.routes.dispatch_task", dummy)

    client = _app()
    resp = client.post(
        "/api/mind-palace/agent/query?background=true",
        json={"question": "system design", "history": [], "context": {}},
    )
    assert resp.status_code == 202
    assert resp.json() == {"task_id": "agent-task-1", "status_url": "/tasks/agent-task-1"}

    assert dummy.sent[0]["name"] == "alfred.tasks.mind_palace_agent.query"
    assert dummy.sent[0]["queue"] == "agent"
    assert dummy.sent[0]["kwargs"]["question"] == "system design"


def test_agent_query_async_legacy_endpoint_removed():
    client = _app()
    resp = client.post(
        "/api/mind-palace/agent/query/async",
        json={"question": "system design", "history": [], "context": {}},
    )
    assert resp.status_code == 404
