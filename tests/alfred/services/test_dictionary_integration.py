"""Integration test for the full dictionary lookup pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alfred.services.dictionary_service import DictionaryResult, lookup


@pytest.mark.asyncio
async def test_lookup_merges_all_sources():
    """Verify lookup() calls all three sources and merges results."""
    mock_wiktionary_response = {
        "en": [
            {
                "partOfSpeech": "Adjective",
                "language": "English",
                "definitions": [
                    {
                        "definition": "Lasting for a short period of time.",
                        "examples": [],
                    },
                ],
            },
        ]
    }

    mock_wikipedia_result = {
        "query": "ephemeral",
        "items": [
            {
                "title": "Ephemeral",
                "content": "In philosophy, the ephemeral...",
            }
        ],
    }

    mock_llm = MagicMock()
    mock_llm.chat_async = AsyncMock(
        return_value="In system design, ephemeral means..."
    )

    with (
        patch(
            "alfred.services.dictionary_service.httpx.AsyncClient"
        ) as MockClient,
        patch(
            "alfred.services.dictionary_service.retrieve_wikipedia"
        ) as mock_wiki,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_wiktionary_response

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(
            return_value=mock_client_instance
        )
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client_instance

        mock_wiki.return_value = mock_wikipedia_result

        result = await lookup(
            "ephemeral", user_domains=["system_design"], llm=mock_llm
        )

    assert isinstance(result, DictionaryResult)
    assert result.word == "ephemeral"
    assert len(result.definitions) == 1
    assert result.definitions[0].part_of_speech == "Adjective"
    assert result.wikipedia_summary == "In philosophy, the ephemeral..."
    assert result.ai_explanation == "In system design, ephemeral means..."
    assert len(result.source_urls) == 2


@pytest.mark.asyncio
async def test_lookup_graceful_degradation():
    """Verify lookup still returns a result when sources fail."""
    mock_llm = MagicMock()
    mock_llm.chat_async = AsyncMock(side_effect=Exception("LLM down"))

    with (
        patch(
            "alfred.services.dictionary_service.httpx.AsyncClient"
        ) as MockClient,
        patch(
            "alfred.services.dictionary_service.retrieve_wikipedia"
        ) as mock_wiki,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(
            return_value=mock_client_instance
        )
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client_instance

        mock_wiki.side_effect = Exception("Wikipedia down")

        result = await lookup("nonexistent", llm=mock_llm)

    assert isinstance(result, DictionaryResult)
    assert result.word == "nonexistent"
    assert result.definitions == []
    assert result.wikipedia_summary is None
    assert result.ai_explanation is None
