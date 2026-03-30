"""Tests for AlfredAgentState schema."""

from __future__ import annotations

import typing

from langchain_core.messages import HumanMessage

from alfred.agents.orchestrator.state import AlfredAgentState


def test_state_accepts_minimal_fields():
    state: AlfredAgentState = {
        "messages": [HumanMessage(content="hello")],
        "thread_id": "t-1",
        "model": "gpt-4.1-mini",
        "iteration": 0,
    }
    assert state["thread_id"] == "t-1"
    assert len(state["messages"]) == 1


def test_state_optional_fields_default_none():
    state: AlfredAgentState = {
        "messages": [],
        "thread_id": "t-2",
        "model": "gpt-4.1-mini",
        "iteration": 0,
    }
    assert state.get("note_context") is None
    assert state.get("intent") is None


def test_state_with_intent():
    state: AlfredAgentState = {
        "messages": [],
        "thread_id": "t-3",
        "model": "gpt-4.1-mini",
        "iteration": 0,
        "intent": "summarize",
        "intent_args": {"url": "https://example.com"},
    }
    assert state["intent"] == "summarize"
    assert state["intent_args"]["url"] == "https://example.com"


def test_messages_annotation_supports_add():
    hints = typing.get_type_hints(AlfredAgentState, include_extras=True)
    meta = typing.get_args(hints["messages"])
    assert len(meta) >= 2, "messages should be Annotated with a reducer"
