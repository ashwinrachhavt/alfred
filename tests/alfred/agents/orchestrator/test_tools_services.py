"""Tests for Phase 2 service tools (summarize, diagram, plan, edit, autocomplete)."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from alfred.agents.orchestrator.tools.services import (
    make_autocomplete_tool,
    make_create_plan_tool,
    make_edit_text_tool,
    make_generate_diagram_tool,
    make_summarize_tool,
)

# --- Summarize ---


@dataclass
class FakeSummaryPayload:
    title: str = "Test Title"
    short: str = "A short summary."
    bullets: list = None
    key_points: list = None
    language: str = "en"

    def __post_init__(self):
        if self.bullets is None:
            self.bullets = ["Point 1", "Point 2"]
        if self.key_points is None:
            self.key_points = ["Key insight"]


def test_summarize_content():
    mock_svc = MagicMock()
    mock_svc.summarize_text.return_value = (FakeSummaryPayload(), None)

    with patch(
        "alfred.agents.orchestrator.tools.services.get_summarization_service",
        return_value=mock_svc,
    ):
        tool = make_summarize_tool()
        result = tool.invoke({"text": "Long article text here"})

    assert "summarized" in result
    assert "short summary" in result.lower() or "short" in result
    mock_svc.summarize_text.assert_called_once()


# --- Diagram ---


def test_generate_diagram():
    mock_model = MagicMock()
    mock_model.invoke.return_value = MagicMock(content='{"elements": [{"id": "1", "type": "rectangle"}], "description": "A box"}')

    with patch(
        "alfred.agents.orchestrator.tools.services.get_chat_model",
        return_value=mock_model,
    ), patch(
        "alfred.agents.orchestrator.tools.services.build_diagram_prompt",
        return_value="prompt text",
    ), patch(
        "alfred.agents.orchestrator.tools.services.parse_diagram_response",
        return_value={"elements": [{"id": "1", "type": "rectangle"}], "description": "A box"},
    ):
        tool = make_generate_diagram_tool()
        result = tool.invoke({"prompt": "Draw a flowchart"})

    assert "diagram_generated" in result
    assert "element_count" in result


# --- Plan ---


@dataclass
class FakePlanStep:
    step: str = "Do something"
    status: str = "pending"


@dataclass
class FakeExecutionPlan:
    id: str = "plan-1"
    goal: str = "Build a thing"
    steps: list = None

    def __post_init__(self):
        if self.steps is None:
            self.steps = [FakePlanStep("Step 1"), FakePlanStep("Step 2")]


def test_create_plan():
    mock_svc = MagicMock()
    mock_svc.create_plan.return_value = FakeExecutionPlan()

    with patch(
        "alfred.agents.orchestrator.tools.services.get_planning_service",
        return_value=mock_svc,
    ):
        tool = make_create_plan_tool()
        result = tool.invoke({"goal": "Build a knowledge graph"})

    assert "plan_created" in result
    assert "Step 1" in result
    mock_svc.create_plan.assert_called_once()


# --- Edit Text ---


@dataclass
class FakeTextEditResponse:
    output: str = "Edited text here."
    language: str = "en"


def test_edit_text():
    mock_svc = MagicMock()
    mock_svc.edit.return_value = FakeTextEditResponse()

    with patch(
        "alfred.agents.orchestrator.tools.services.get_text_assist_service",
        return_value=mock_svc,
    ):
        tool = make_edit_text_tool()
        result = tool.invoke({"text": "Some rough text", "instruction": "Make it concise"})

    assert "text_edited" in result
    assert "Edited text here" in result
    mock_svc.edit.assert_called_once()


# --- Autocomplete ---


@dataclass
class FakeAutocompleteResponse:
    completion: str = "...and that is why AI matters."
    language: str = "en"


def test_autocomplete():
    mock_svc = MagicMock()
    mock_svc.autocomplete.return_value = FakeAutocompleteResponse()

    with patch(
        "alfred.agents.orchestrator.tools.services.get_text_assist_service",
        return_value=mock_svc,
    ):
        tool = make_autocomplete_tool()
        result = tool.invoke({"text": "The reason AI is important is"})

    assert "autocompleted" in result
    assert "AI matters" in result
    mock_svc.autocomplete.assert_called_once()
