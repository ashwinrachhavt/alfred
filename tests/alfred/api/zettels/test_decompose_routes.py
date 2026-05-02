"""Tests for the SSE decompose-stream route (T5)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.dependencies import get_db_session
from alfred.api.zettels.routes import router as zettels_router
from alfred.services.zettel_decompose_stream import _sse


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(zettels_router)
    # Other routes on this router depend on get_db_session — inject a stub
    # so the app wiring succeeds.
    app.dependency_overrides[get_db_session] = lambda: MagicMock()
    return TestClient(app)


def test_decompose_stream_endpoint_returns_sse(client: TestClient) -> None:
    """POST to /api/zettels/decompose-stream should return text/event-stream."""

    async def _fake_run(self):
        yield _sse("decompose_started", {"raw_char_count": 10, "shared_topic": None})
        yield _sse(
            "candidate_ready",
            {
                "index": 0,
                "title": "T",
                "content": "C",
                "bloom_level": 1,
                "bloom_rationale": "",
                "tags": [],
                "links_to_siblings": [],
            },
        )
        yield _sse("decompose_complete", {"total_candidates": 1})

    with patch(
        "alfred.api.zettels.routes.ZettelDecomposeStream.run",
        _fake_run,
    ):
        response = client.post(
            "/api/zettels/decompose-stream",
            json={"raw_text": "A paragraph."},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: decompose_started" in response.text
    assert "event: decompose_complete" in response.text


def test_decompose_stream_endpoint_has_sse_headers(client: TestClient) -> None:
    """The response should include SSE-specific headers."""

    async def _fake_run(self):
        yield _sse("decompose_complete", {"total_candidates": 0})

    with patch(
        "alfred.api.zettels.routes.ZettelDecomposeStream.run",
        _fake_run,
    ):
        response = client.post(
            "/api/zettels/decompose-stream",
            json={"raw_text": "Paragraph."},
        )

    assert response.headers.get("cache-control") == "no-cache"
    assert response.headers.get("x-accel-buffering") == "no"
    assert response.headers.get("connection") == "keep-alive"
