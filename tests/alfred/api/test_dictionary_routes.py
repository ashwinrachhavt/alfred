"""Tests for dictionary API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
            senses=[
                DefinitionSense(
                    definition="Lasting briefly", examples=["An ephemeral joy."]
                )
            ],
        )
    ],
    etymology="From Greek ephemeros",
    wikipedia_summary="In philosophy...",
    ai_explanation="In system design...",
    source_urls=["https://en.wiktionary.org/wiki/ephemeral"],
)


class TestLookupEndpoint:
    def test_lookup_returns_result(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from alfred.api.dictionary.routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch(
            "alfred.api.dictionary.routes.lookup", new_callable=AsyncMock
        ) as mock_lookup:
            mock_lookup.return_value = MOCK_RESULT
            resp = client.get("/api/dictionary/lookup?word=ephemeral")

        assert resp.status_code == 200
        data = resp.json()
        assert data["word"] == "ephemeral"
        assert data["pronunciation_ipa"] == "/ephemeral/"
        assert len(data["definitions"]) == 1
        assert data["definitions"][0]["part_of_speech"] == "Adjective"
