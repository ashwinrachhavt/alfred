from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.admin import routes as admin_routes


def _client(*, monkeypatch, pending: int = 3, total: int = 10, sample_ids=None) -> TestClient:
    sample_ids = sample_ids or [101, 102]

    class _FakeResult:
        def __init__(self, val: int) -> None:
            self._val = val

        def one(self) -> int:
            return self._val

    class _FakeSession:
        def __init__(self) -> None:
            self._calls = 0

        def exec(self, _stmt):
            self._calls += 1
            # Route does 2 exec() calls (pending, total). Keep it deterministic.
            if self._calls == 1:
                return _FakeResult(pending)
            return _FakeResult(total)

    def _fake_get_db_session():
        yield _FakeSession()

    def _fake_list(self, *, limit, topic_id, min_age_hours, force):
        return [SimpleNamespace(id=i) for i in sample_ids[:limit]]

    monkeypatch.setattr(
        admin_routes.LearningService, "list_resources_needing_extraction", _fake_list
    )

    app = FastAPI()
    app.include_router(admin_routes.router)
    app.dependency_overrides[admin_routes.get_db_session] = _fake_get_db_session
    return TestClient(app)


def test_learning_concepts_backlog(monkeypatch) -> None:
    client = _client(monkeypatch=monkeypatch, pending=5, total=12, sample_ids=[7, 8, 9])
    resp = client.get("/api/admin/learning/concepts/backlog")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_count"] == 5
    assert data["total_with_document"] == 12
    assert data["sample_resource_ids"] == [7, 8, 9]
    assert "nightly" in data
    assert set(data["nightly"].keys()) == {
        "enabled",
        "utc_hour",
        "utc_minute",
        "batch_limit",
        "min_age_hours",
    }


def test_admin_enqueue_learning_concepts_batch(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(admin_routes.router)
    client = TestClient(app)

    class _FakeAsyncResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id

    class _FakeCelery:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def send_task(self, name: str, *, kwargs: dict) -> _FakeAsyncResult:
            self.calls.append({"name": name, "kwargs": kwargs})
            return _FakeAsyncResult("task-abc")

    fake_celery = _FakeCelery()
    monkeypatch.setattr(admin_routes, "get_celery_client", lambda: fake_celery)

    resp = client.post(
        "/api/admin/learning/concepts/extract/batch/async",
        json={"limit": 25, "topic_id": 7, "min_age_hours": 6, "force": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["task_id"] == "task-abc"
    assert data["status_url"] == "/tasks/task-abc"
    assert fake_celery.calls == [
        {
            "name": "alfred.tasks.learning_concepts.batch_extract",
            "kwargs": {
                "limit": 25,
                "topic_id": 7,
                "min_age_hours": 6,
                "force": True,
                "enqueue_only": True,
            },
        }
    ]
