"""Tests for zettel decomposition service."""

from __future__ import annotations

import json

import pytest

from alfred.services.zettel_decomposer import (
    MAX_CARDS,
    TEXT_TRUNCATE_LIMIT,
    build_decomposition_prompt,
    parse_decomposition_response,
)


class TestBuildDecompositionPrompt:
    """Tests for build_decomposition_prompt."""

    def test_prompt_includes_document_context(self):
        """Prompt should include title and topics."""
        prompt = build_decomposition_prompt(
            title="Test Document",
            summary="This is a summary",
            cleaned_text="Full text content here",
            topics={"primary": "philosophy", "secondary": ["epistemology", "metaphysics"]},
        )

        assert "Test Document" in prompt
        assert "philosophy" in prompt
        assert "epistemology" in prompt
        assert "This is a summary" in prompt

    def test_prompt_limits_text_length(self):
        """Long text should be truncated to TEXT_TRUNCATE_LIMIT."""
        long_text = "x" * (TEXT_TRUNCATE_LIMIT + 1000)

        prompt = build_decomposition_prompt(
            title="Long Doc",
            summary=None,
            cleaned_text=long_text,
            topics=None,
        )

        # The prompt should not contain the full long_text
        # Check that text is truncated
        assert long_text not in prompt
        assert "x" * TEXT_TRUNCATE_LIMIT in prompt

    def test_handles_missing_optional_fields(self):
        """Should handle None values for summary and topics gracefully."""
        prompt = build_decomposition_prompt(
            title="Minimal Doc",
            summary=None,
            cleaned_text="Just some text",
            topics=None,
        )

        assert "Minimal Doc" in prompt
        assert "Just some text" in prompt
        # Should not crash


class TestParseDecompositionResponse:
    """Tests for parse_decomposition_response."""

    def test_parses_valid_json_array(self):
        """Should parse valid JSON array with title, content, tags."""
        response = json.dumps([
            {
                "title": "First Concept",
                "content": "This is the first concept explanation.",
                "tags": ["tag1", "tag2"],
            },
            {
                "title": "Second Concept",
                "content": "This is the second concept explanation.",
                "tags": ["tag3"],
            },
        ])

        cards = parse_decomposition_response(response)

        assert len(cards) == 2
        assert cards[0]["title"] == "First Concept"
        assert cards[0]["content"] == "This is the first concept explanation."
        assert cards[0]["tags"] == ["tag1", "tag2"]
        assert cards[1]["title"] == "Second Concept"

    def test_handles_markdown_code_fence(self):
        """Should strip ```json``` fences before parsing."""
        response = """```json
[
  {
    "title": "Fenced Concept",
    "content": "Content here.",
    "tags": ["test"]
  }
]
```"""

        cards = parse_decomposition_response(response)

        assert len(cards) == 1
        assert cards[0]["title"] == "Fenced Concept"

    def test_returns_empty_on_invalid_json(self):
        """Should return empty list on invalid JSON."""
        response = "This is not JSON at all"

        cards = parse_decomposition_response(response)

        assert cards == []

    def test_caps_at_max_cards(self):
        """Should cap output at MAX_CARDS even if more are provided."""
        many_cards = [
            {
                "title": f"Card {i}",
                "content": f"Content {i}",
                "tags": ["tag"],
            }
            for i in range(20)
        ]
        response = json.dumps(many_cards)

        cards = parse_decomposition_response(response)

        assert len(cards) == MAX_CARDS

    def test_handles_missing_tags_field(self):
        """Should add empty tags list if not provided."""
        response = json.dumps([
            {
                "title": "No Tags",
                "content": "Content without tags.",
            }
        ])

        cards = parse_decomposition_response(response)

        assert len(cards) == 1
        assert cards[0]["tags"] == []

    def test_filters_invalid_cards(self):
        """Should filter out cards missing required fields."""
        response = json.dumps([
            {"title": "Valid", "content": "Good card", "tags": []},
            {"title": "No content"},  # Missing content
            {"content": "No title"},  # Missing title
            {},  # Empty
            "not a dict",
            {"title": "Valid 2", "content": "Another good card", "tags": ["a"]},
        ])

        cards = parse_decomposition_response(response)

        # Should only have the 2 valid cards
        assert len(cards) == 2
        assert cards[0]["title"] == "Valid"
        assert cards[1]["title"] == "Valid 2"

    def test_returns_empty_on_non_array_response(self):
        """Should return empty list if response is not a JSON array."""
        response = json.dumps({"title": "Single object", "content": "Not an array"})

        cards = parse_decomposition_response(response)

        assert cards == []
