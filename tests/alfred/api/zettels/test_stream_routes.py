"""Tests for the SSE streaming zettel creation route."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.dependencies import get_db_session
from alfred.api.zettels.routes import router as zettels_router
from alfred.services.zettel_creation_stream import _sse


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(zettels_router)
    # Override DB dependency (route doesn't use it, but other routes on this
    # router do, so we need a valid override for app setup).
    from unittest.mock import MagicMock

    app.dependency_overrides[get_db_session] = lambda: MagicMock()
    return TestClient(app)


def test_create_stream_endpoint_returns_sse(client: TestClient) -> None:
    """POST to /api/zettels/cards/create-stream should return text/event-stream."""

    async def _fake_run(self):
        yield _sse("card_saved", {"id": 1, "title": "Test", "status": "active"})
        yield _sse("done", {"card": {"id": 1, "title": "Test"}, "stats": {"card_id": 1}})

    with patch(
        "alfred.api.zettels.routes.ZettelCreationStream.run",
        _fake_run,
    ):
        response = client.post(
            "/api/zettels/cards/create-stream",
            json={"title": "Stream Test Card", "content": "Content for streaming"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: card_saved" in response.text
    assert "event: done" in response.text


def test_create_stream_endpoint_has_sse_headers(client: TestClient) -> None:
    """The response should include SSE-specific headers."""

    async def _fake_run(self):
        yield _sse("done", {"card": None, "stats": {}})

    with patch(
        "alfred.api.zettels.routes.ZettelCreationStream.run",
        _fake_run,
    ):
        response = client.post(
            "/api/zettels/cards/create-stream",
            json={"title": "Header Test", "content": "Content"},
        )

    assert response.headers.get("cache-control") == "no-cache"
    assert response.headers.get("x-accel-buffering") == "no"
