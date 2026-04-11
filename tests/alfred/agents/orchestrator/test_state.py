"""Tests for AlfredAgentState schema."""

from __future__ import annotations

import typing

from langchain_core.messages import HumanMessage

from alfred.agents.orchestrator.state import AlfredAgentState


def test_state_accepts_minimal_fields():
    state: AlfredAgentState = {
        "messages": [HumanMessage(content="hello")],
        "thread_id": "t-1",
        "model": "gpt-5.4",
    }
    assert state["thread_id"] == "t-1"
    assert len(state["messages"]) == 1


def test_state_optional_fields_default_none_or_empty():
    state: AlfredAgentState = {
        "messages": [],
        "thread_id": "t-2",
        "model": "gpt-5.4",
    }
    assert state.get("note_context") is None
    assert state.get("intent") is None
    assert state.get("plan") is None
    assert state.get("pending_approvals") is None


def test_state_accepts_planner_fields():
    state: AlfredAgentState = {
        "messages": [],
        "thread_id": "t-3",
        "model": "gpt-5.4",
        "plan": [
            {
                "id": "task-1",
                "agent": "knowledge",
                "objective": "Search Alfred's knowledge base",
                "context_refs": ["messages"],
                "mode": "read",
                "status": "queued",
            }
        ],
        "task_results": [],
        "pending_approvals": [],
    }
    assert state["plan"][0]["agent"] == "knowledge"
    assert state["plan"][0]["status"] == "queued"


def test_messages_annotation_supports_add():
    hints = typing.get_type_hints(AlfredAgentState, include_extras=True)
    meta = typing.get_args(hints["messages"])
    assert len(meta) >= 2, "messages should be Annotated with a reducer"


def test_worker_result_annotations_support_add():
    hints = typing.get_type_hints(AlfredAgentState, include_extras=True)
    task_result_meta = typing.get_args(hints["task_results"])
    artifacts_meta = typing.get_args(hints["artifacts"])
    assert len(task_result_meta) >= 2
    assert len(artifacts_meta) >= 2
