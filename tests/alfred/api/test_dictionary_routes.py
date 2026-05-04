"""Tests for dictionary API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.services.dictionary_service import (
    DefinitionGroup,
    DefinitionSense,
    DictionaryResult,
)

MOCK_RESULT = DictionaryResult(
    word="ephemeral",
    pronunciation_ipa="/ephemeral/",
    definitions=[
        DefinitionGroup(
            part_of_speech="Adjective",
            senses=[DefinitionSense(definition="Lasting briefly", examples=["An ephemeral joy."])],
        )
    ],
    etymology="From Greek ephemeros",
    wikipedia_summary="In philosophy...",
    ai_explanation="In system design...",
    source_urls=["https://en.wiktionary.org/wiki/ephemeral"],
)


def _client() -> TestClient:
    from alfred.api.dictionary.routes import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestLookupEndpoint:
    def test_lookup_returns_result(self):
        client = _client()

        with patch("alfred.api.dictionary.routes.lookup", new_callable=AsyncMock) as mock_lookup:
            mock_lookup.return_value = MOCK_RESULT
            resp = client.get("/api/dictionary/lookup?word=ephemeral")

        assert resp.status_code == 200
        data = resp.json()
        assert data["word"] == "ephemeral"
        assert data["pronunciation_ipa"] == "/ephemeral/"
        assert len(data["definitions"]) == 1
        assert data["definitions"][0]["part_of_speech"] == "Adjective"
        mock_lookup.assert_awaited_once_with("ephemeral", llm=None)


class TestSearchEndpoint:
    def test_search_does_not_perform_external_lookup(self):
        client = _client()

        with (
            patch("alfred.api.dictionary.routes._search_saved_entries") as mock_saved,
            patch("alfred.api.dictionary.routes.lookup", new_callable=AsyncMock) as mock_lookup,
        ):
            mock_saved.return_value = []
            resp = client.get("/api/dictionary/search?q=ep")

        assert resp.status_code == 200
        assert resp.json() == {"query": "ep", "saved": [], "lookup": None}
        mock_saved.assert_called_once_with("ep")
        mock_lookup.assert_not_awaited()


class TestLookupStreamEndpoint:
    def test_lookup_stream_returns_sse_events(self):
        client = _client()

        async def fake_stream(*_args, **_kwargs):
            yield ("lookup", MOCK_RESULT.to_dict() | {"ai_explanation": None})
            yield ("ai_delta", {"content": "In context"})
            yield ("done", MOCK_RESULT.to_dict())

        with patch(
            "alfred.api.dictionary.routes.lookup_stream_events",
            side_effect=fake_stream,
        ) as mock_stream:
            resp = client.get("/api/dictionary/lookup/stream?word=ephemeral")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert "event: lookup" in resp.text
        assert "event: ai_delta" in resp.text
        assert "event: done" in resp.text
        mock_stream.assert_called_once()
