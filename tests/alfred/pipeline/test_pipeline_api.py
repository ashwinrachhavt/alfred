from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.pipeline import router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_replay_endpoint(client: TestClient):
    mock_celery = MagicMock()
    mock_celery.send_task.return_value = MagicMock(id="task-123")

    with patch("alfred.api.pipeline.routes.get_celery_client", return_value=mock_celery):
        resp = client.post("/api/pipeline/d1/replay", params={"force": True})

    assert resp.status_code == 202
    body = resp.json()
    assert body["doc_id"] == "d1"
    assert body["task_id"] == "task-123"
    mock_celery.send_task.assert_called_once()


def test_status_endpoint(client: TestClient):
    mock_checkpointer = MagicMock()
    mock_checkpointer.get_tuple.return_value = MagicMock(
        checkpoint={
            "channel_values": {
                "stage": "persist",
                "errors": [],
                "cache_hits": ["extract"],
            }
        },
    )

    with patch(
        "alfred.api.pipeline.routes._get_checkpointer",
        return_value=mock_checkpointer,
    ):
        resp = client.get("/api/pipeline/d1/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["stage"] == "persist"


def test_status_not_found(client: TestClient):
    mock_checkpointer = MagicMock()
    mock_checkpointer.get_tuple.return_value = None

    with patch(
        "alfred.api.pipeline.routes._get_checkpointer",
        return_value=mock_checkpointer,
    ):
        resp = client.get("/api/pipeline/d1/status")

    assert resp.status_code == 404
