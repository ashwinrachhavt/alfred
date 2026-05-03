"""Unit tests for the shared parts[] accumulator helpers used by both the
v1 SSE route and the v2 MessageProjector.

These helpers mirror the frontend agent-store.ts parts construction, so the
DB row round-trips to the same canonical AI Elements shape the UI emits live.
"""

from __future__ import annotations

from alfred.streaming.projectors._parts import (
    finalize_streaming_parts,
    handle_error,
    handle_reasoning,
    handle_token,
    handle_tool_result,
    handle_tool_start,
)


def test_handle_token_extends_trailing_streaming_text_part() -> None:
    parts: list[dict] = []
    handle_token(parts, "Hello ")
    handle_token(parts, "world")
    assert len(parts) == 1
    assert parts[0] == {"type": "text", "text": "Hello world", "state": "streaming"}


def test_text_tool_text_sequence_produces_three_parts() -> None:
    """Mirrors the frontend: text → tool → text → tool_result → 3 parts total
    (text done, tool output-available, text streaming)."""
    parts: list[dict] = []
    # tokens streamed
    handle_token(parts, "I'll ")
    handle_token(parts, "search.")
    # then a tool fires — must finalize the streaming text first
    handle_tool_start(parts, tool_name="search_kb", call_id="call-1", args={"q": "topic"}, now_ms=1_000)
    # then result comes back
    handle_tool_result(parts, call_id="call-1", result={"hits": ["a", "b"]})
    # then more tokens
    handle_token(parts, "Found ")
    handle_token(parts, "two.")

    assert len(parts) == 3
    # First part: text (done because finalized when the tool fired)
    assert parts[0]["type"] == "text"
    assert parts[0]["text"] == "I'll search."
    assert parts[0]["state"] == "done"
    # Second part: tool with output
    assert parts[1]["type"] == "tool-search_kb"
    assert parts[1]["toolCallId"] == "call-1"
    assert parts[1]["state"] == "output-available"
    assert parts[1]["input"] == {"q": "topic"}
    assert parts[1]["output"] == {"hits": ["a", "b"]}
    # Third part: still-streaming text
    assert parts[2]["type"] == "text"
    assert parts[2]["text"] == "Found two."
    assert parts[2]["state"] == "streaming"


def test_tool_result_error_sets_output_error_and_error_text() -> None:
    parts: list[dict] = []
    handle_tool_start(parts, tool_name="search_kb", call_id="c1", args={}, now_ms=1)
    handle_tool_result(parts, call_id="c1", result={"error": "boom"})
    assert parts[-1]["state"] == "output-error"
    assert parts[-1]["errorText"] == "boom"


def test_tool_result_without_call_id_uses_input_available_fallback() -> None:
    """Legacy backends may omit call_id on tool_result — frontend matches the
    last ``input-available`` tool part; the helper must do the same."""
    parts: list[dict] = []
    handle_tool_start(parts, tool_name="get_zettel", call_id="", args={"id": 1}, now_ms=0)
    handle_tool_result(parts, call_id="", result={"zettel": {"id": 1}})
    assert parts[-1]["state"] == "output-available"
    assert parts[-1]["output"] == {"zettel": {"id": 1}}


def test_finalize_streaming_parts_closes_text_and_stamps_reasoning() -> None:
    parts: list[dict] = []
    handle_token(parts, "streaming text")
    handle_reasoning(parts, "thinking out loud", now_ms=10)
    finalize_streaming_parts(parts, now_ms=99)
    # Note: handle_reasoning was called AFTER handle_token, so it replaces the
    # trailing part behaviour — each helper only extends a matching trailing
    # part. The current trailing is a reasoning part, so the text part above
    # is not streaming any longer when reasoning started; verify state.
    # text part should still be present and finalized
    assert parts[0]["type"] == "text"
    assert parts[0]["state"] == "done"
    # reasoning part should be finalized with finishedAt
    assert parts[1]["type"] == "reasoning"
    assert parts[1]["state"] == "done"
    assert parts[1]["startedAt"] == 10
    assert parts[1]["finishedAt"] == 99


def test_handle_reasoning_extends_trailing_streaming_reasoning() -> None:
    parts: list[dict] = []
    handle_reasoning(parts, "First ", now_ms=1)
    handle_reasoning(parts, "second.", now_ms=2)
    assert len(parts) == 1
    assert parts[0]["type"] == "reasoning"
    assert parts[0]["text"] == "First second."
    assert parts[0]["state"] == "streaming"
    assert parts[0]["startedAt"] == 1  # preserved from first call


def test_handle_error_finalizes_then_appends_done_text_part() -> None:
    parts: list[dict] = []
    handle_token(parts, "in progress...")
    handle_error(parts, "Something broke", now_ms=42)
    assert len(parts) == 2
    assert parts[0]["state"] == "done"
    assert parts[1] == {"type": "text", "text": "Something broke", "state": "done"}
