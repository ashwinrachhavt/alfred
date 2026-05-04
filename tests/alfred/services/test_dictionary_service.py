"""Tests for dictionary service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

WIKTIONARY_RESPONSE = {
    "en": [
        {
            "partOfSpeech": "Adjective",
            "language": "English",
            "definitions": [
                {
                    "definition": "Lasting for a short period of time.",
                    "examples": ["Ephemeral pleasures are soon forgotten."],
                },
                {
                    "definition": "Existing for only one day, as with certain insects.",
                    "examples": [],
                },
            ],
        },
        {
            "partOfSpeech": "Noun",
            "language": "English",
            "definitions": [
                {
                    "definition": "Something that is ephemeral.",
                    "examples": [],
                },
            ],
        },
    ]
}


class TestParseWiktionaryResponse:
    def test_parse_definitions(self):
        from alfred.services.dictionary_service import _parse_wiktionary_response

        result = _parse_wiktionary_response(WIKTIONARY_RESPONSE)
        assert len(result["definitions"]) == 2

        adj = result["definitions"][0]
        assert adj["part_of_speech"] == "Adjective"
        assert len(adj["senses"]) == 2
        assert adj["senses"][0]["definition"] == "Lasting for a short period of time."
        assert adj["senses"][0]["examples"] == ["Ephemeral pleasures are soon forgotten."]

        noun = result["definitions"][1]
        assert noun["part_of_speech"] == "Noun"
        assert len(noun["senses"]) == 1

    def test_parse_empty_response(self):
        from alfred.services.dictionary_service import _parse_wiktionary_response

        result = _parse_wiktionary_response({})
        assert result["definitions"] == []

    def test_parse_non_english_filtered(self):
        from alfred.services.dictionary_service import _parse_wiktionary_response

        response = {
            "en": [
                {
                    "partOfSpeech": "Adjective",
                    "language": "English",
                    "definitions": [
                        {"definition": "English def", "examples": []},
                    ],
                },
            ],
            "fr": [
                {
                    "partOfSpeech": "Adjectif",
                    "language": "French",
                    "definitions": [
                        {"definition": "French def", "examples": []},
                    ],
                },
            ],
        }
        result = _parse_wiktionary_response(response)
        assert len(result["definitions"]) == 1
        assert result["definitions"][0]["part_of_speech"] == "Adjective"


class TestMergeLookupResult:
    def test_merge_builds_complete_result(self):
        from alfred.services.dictionary_service import DictionaryResult, _merge_results

        wiktionary_data = {
            "definitions": [
                {
                    "part_of_speech": "Adjective",
                    "senses": [
                        {"definition": "Lasting briefly", "examples": ["An ephemeral joy."]},
                    ],
                },
            ],
            "pronunciation_ipa": "/ephemeral/",
            "etymology": "From Greek ephemeros",
        }
        wikipedia_summary = "In philosophy, the ephemeral is..."
        ai_explanation = "In system design, ephemeral means short-lived..."

        result = _merge_results(
            word="ephemeral",
            wiktionary=wiktionary_data,
            wikipedia_summary=wikipedia_summary,
            ai_explanation=ai_explanation,
        )

        assert isinstance(result, DictionaryResult)
        assert result.word == "ephemeral"
        assert result.pronunciation_ipa == "/ephemeral/"
        assert result.etymology == "From Greek ephemeros"
        assert result.wikipedia_summary == "In philosophy, the ephemeral is..."
        assert result.ai_explanation == "In system design, ephemeral means short-lived..."
        assert len(result.definitions) == 1

    def test_merge_handles_missing_sources(self):
        from alfred.services.dictionary_service import DictionaryResult, _merge_results

        result = _merge_results(
            word="test",
            wiktionary={"definitions": [], "pronunciation_ipa": None, "etymology": None},
            wikipedia_summary=None,
            ai_explanation=None,
        )

        assert isinstance(result, DictionaryResult)
        assert result.word == "test"
        assert result.definitions == []
        assert result.wikipedia_summary is None
        assert result.ai_explanation is None


@pytest.mark.asyncio
async def test_lookup_stream_yields_lookup_before_ai_tokens():
    from alfred.services.dictionary_service import lookup_stream_events

    mock_llm = MagicMock()
    mock_llm.chat_stream.return_value = iter(["In ", "context."])
    wiktionary = {
        "definitions": [
            {
                "part_of_speech": "Adjective",
                "senses": [
                    {"definition": "Lasting briefly.", "examples": []},
                ],
            }
        ],
        "pronunciation_ipa": None,
        "etymology": None,
    }

    async def fake_wikipedia(_word: str) -> str:
        return "A short encyclopedia summary."

    with (
        patch(
            "alfred.services.dictionary_service._fetch_wiktionary",
            return_value=wiktionary,
        ),
        patch(
            "alfred.services.dictionary_service._fetch_wikipedia",
            side_effect=fake_wikipedia,
        ),
    ):
        events = [event async for event in lookup_stream_events("ephemeral", llm=mock_llm)]

    assert events[0][0] == "status"
    assert events[1][0] == "lookup"
    assert events[1][1]["word"] == "ephemeral"
    assert events[1][1]["ai_explanation"] is None
    assert ("ai_delta", {"content": "In "}) in events
    assert ("ai_delta", {"content": "context."}) in events
    assert events[-1][0] == "done"
    assert events[-1][1]["ai_explanation"] == "In context."
    assert events[-1][1]["wikipedia_summary"] == "A short encyclopedia summary."
