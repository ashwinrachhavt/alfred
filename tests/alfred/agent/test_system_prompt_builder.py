"""Tests for SystemPromptBuilder — composable agent prompts."""

from __future__ import annotations

from unittest.mock import patch

from alfred.services.agent.prompts import LENS_PROMPTS, SystemPromptBuilder


@patch("alfred.services.knowledge_notifications.get_pending_notifications", return_value=[])
def test_base_personality_no_forced_search(_mock):
    """Prompt should NOT contain 'ALWAYS search first' or 'NEVER answer from memory'."""
    builder = SystemPromptBuilder()
    prompt = builder.build()

    assert "Alfred" in prompt
    assert "ALWAYS search first" not in prompt
    assert "NEVER answer from memory" not in prompt
    assert "Default to searching" not in prompt
    assert "NOT a generic chatbot" not in prompt

    # Should encourage natural conversation
    assert "normal conversations" in prompt.lower() or "not everything requires" in prompt.lower()


@patch("alfred.services.knowledge_notifications.get_pending_notifications", return_value=[])
def test_tool_guidance_present(_mock):
    """Prompt should include tool-by-tool guidance to help LLM pick correctly."""
    builder = SystemPromptBuilder()
    prompt = builder.build()

    assert "search_kb" in prompt
    assert "create_zettel" in prompt
    assert "web_search_searxng" in prompt or "search_web" in prompt
    assert "generate_quiz" in prompt


@patch("alfred.services.knowledge_notifications.get_pending_notifications", return_value=[])
def test_lens_modifier(_mock):
    """Lens modifier should be appended when provided."""
    builder = SystemPromptBuilder()
    prompt = builder.build(lens="socratic")

    assert "Socratic" in prompt
    assert "probing questions" in prompt.lower()


@patch("alfred.services.knowledge_notifications.get_pending_notifications", return_value=[])
def test_no_lens_when_invalid(_mock):
    """Invalid lens name should not add any modifier."""
    builder = SystemPromptBuilder()
    prompt_with = builder.build(lens="nonexistent_lens")
    prompt_without = builder.build()

    # Both should be the same since invalid lens is ignored
    assert "Active Lens" not in prompt_with
    assert len(prompt_with) == len(prompt_without)


@patch("alfred.services.knowledge_notifications.get_pending_notifications", return_value=[])
def test_note_context_injection(_mock):
    """Note context should appear in prompt when provided."""
    builder = SystemPromptBuilder()
    prompt = builder.build(
        note_context={"title": "Stoic Philosophy", "content_preview": "Marcus Aurelius wrote..."}
    )

    assert "Stoic Philosophy" in prompt
    assert "Marcus Aurelius" in prompt
    assert "Current Note Context" in prompt


@patch("alfred.services.knowledge_notifications.get_pending_notifications", return_value=[])
def test_composition_order(_mock):
    """All sections should compose: personality, tools, style, lens, context."""
    builder = SystemPromptBuilder()
    prompt = builder.build(
        lens="stoic",
        note_context={"title": "Test Note", "content_preview": "Content here"},
    )

    # All sections present
    assert "Alfred" in prompt
    assert "search_kb" in prompt
    assert "Response style" in prompt
    assert "Stoic" in prompt
    assert "Test Note" in prompt


@patch(
    "alfred.services.knowledge_notifications.get_pending_notifications",
    return_value=[
        {"zettel_title": "New Card", "linked_to": [1, 2], "source_document": "Paper.pdf"}
    ],
)
def test_knowledge_notifications_included(mock_notif):
    """Knowledge notifications should appear in prompt when available."""
    builder = SystemPromptBuilder()
    prompt = builder.build()

    assert "New Card" in prompt
    assert "Paper.pdf" in prompt
    assert "linked to 2 existing cards" in prompt


@patch(
    "alfred.services.knowledge_notifications.get_pending_notifications",
    side_effect=Exception("Redis down"),
)
def test_notification_failure_silent(mock_notif):
    """Notification failure should not break prompt building."""
    builder = SystemPromptBuilder()
    prompt = builder.build()

    # Should still have the base prompt
    assert "Alfred" in prompt
    assert "New Knowledge" not in prompt  # Notification section absent


def test_all_lenses_exist():
    """All 7 philosophical lenses should be defined."""
    expected = {"socratic", "stoic", "existentialist", "utilitarian", "kantian", "virtue_ethics", "eastern"}
    assert set(LENS_PROMPTS.keys()) == expected
