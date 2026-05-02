"""Parity fixtures — scripted agent turns + expected AgentMessageRow fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParityFixture:
    """A scripted agent turn with expected persistence fields."""

    id: str
    script: list[tuple[str, dict[str, Any], str]]
    thread_id: int  # ignored at runtime; test creates a real thread_id
    lens: str | None
    model: str | None
    expected: dict[str, Any] | None  # None => expect zero rows written


def _tt(name: str, data: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    """Build a (name, data, '') tuple — sse_str is ignored by the producer."""
    return (name, data, "")


PARITY_FIXTURES: list[ParityFixture] = [
    # 1. simple_text
    ParityFixture(
        id="simple_text",
        script=[
            _tt("token", {"content": "hi"}),
            _tt("token", {"content": "!"}),
            _tt("token", {"content": " there"}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4-mini",
        expected={"content": "hi! there"},
    ),
    # 2. text_with_reasoning
    ParityFixture(
        id="text_with_reasoning",
        script=[
            _tt("reasoning", {"content": "hmm"}),
            _tt("reasoning", {"content": " thinking"}),
            _tt("token", {"content": "ok"}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={"content": "ok", "reasoning_traces": "hmm thinking"},
    ),
    # 3. single_tool_then_text
    ParityFixture(
        id="single_tool_then_text",
        script=[
            _tt(
                "tool_start",
                {
                    "call_id": "c1",
                    "tool": "search_kb",
                    "args": {"q": "epistemology"},
                },
            ),
            _tt(
                "tool_result",
                {
                    "call_id": "c1",
                    "result": {"hits": 3},
                    "status": "ok",
                },
            ),
            _tt("token", {"content": "done"}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={
            "content": "done",
            "tool_calls": [
                {
                    "call_id": "c1",
                    "tool": "search_kb",
                    "args": {"q": "epistemology"},
                    "status": "ok",
                    "result": {"hits": 3},
                }
            ],
        },
    ),
    # 4. two_tools_sequential
    ParityFixture(
        id="two_tools_sequential",
        script=[
            _tt("tool_start", {"call_id": "c1", "tool": "search_kb", "args": {"q": "x"}}),
            _tt("tool_result", {"call_id": "c1", "result": {"hits": 1}, "status": "ok"}),
            _tt("tool_start", {"call_id": "c2", "tool": "create_zettel", "args": {"title": "T"}}),
            _tt("tool_result", {"call_id": "c2", "result": {"id": 42}, "status": "ok"}),
            _tt("token", {"content": "ok"}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={
            "content": "ok",
            "tool_calls": [
                {
                    "call_id": "c1",
                    "tool": "search_kb",
                    "args": {"q": "x"},
                    "status": "ok",
                    "result": {"hits": 1},
                },
                {
                    "call_id": "c2",
                    "tool": "create_zettel",
                    "args": {"title": "T"},
                    "status": "ok",
                    "result": {"id": 42},
                },
            ],
        },
    ),
    # 5. tool_error_status
    ParityFixture(
        id="tool_error_status",
        script=[
            _tt("tool_start", {"call_id": "c1", "tool": "fetch_url", "args": {"u": "x"}}),
            _tt(
                "tool_result",
                {
                    "call_id": "c1",
                    "result": {"error": "failed"},
                    "status": "error",
                },
            ),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={
            "content": "",
            "tool_calls": [
                {
                    "call_id": "c1",
                    "tool": "fetch_url",
                    "args": {"u": "x"},
                    "status": "error",
                    "result": {"error": "failed"},
                }
            ],
        },
    ),
    # 6. single_artifact_no_content
    ParityFixture(
        id="single_artifact_no_content",
        script=[
            _tt(
                "artifact",
                {
                    "type": "zettel",
                    "action": "created",
                    "zettel": {
                        "id": 42,
                        "title": "T",
                        "summary": "",
                        "topic": "",
                        "tags": [],
                    },
                },
            ),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={
            "content": "",
            "artifacts": [
                {
                    "type": "zettel",
                    "action": "created",
                    "zettel": {
                        "id": 42,
                        "title": "T",
                        "summary": "",
                        "topic": "",
                        "tags": [],
                    },
                }
            ],
        },
    ),
    # 7. multiple_artifacts
    ParityFixture(
        id="multiple_artifacts",
        script=[
            _tt("artifact", {"type": "zettel", "action": "created", "zettel": {"id": 1}}),
            _tt("artifact", {"type": "zettel", "action": "created", "zettel": {"id": 2}}),
            _tt("artifact", {"type": "zettel", "action": "created", "zettel": {"id": 3}}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={
            "content": "",
            "artifacts": [
                {"type": "zettel", "action": "created", "zettel": {"id": 1}},
                {"type": "zettel", "action": "created", "zettel": {"id": 2}},
                {"type": "zettel", "action": "created", "zettel": {"id": 3}},
            ],
        },
    ),
    # 8. artifact_with_text
    ParityFixture(
        id="artifact_with_text",
        script=[
            _tt("artifact", {"type": "zettel", "action": "created", "zettel": {"id": 99}}),
            _tt("token", {"content": "saved"}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={
            "content": "saved",
            "artifacts": [{"type": "zettel", "action": "created", "zettel": {"id": 99}}],
        },
    ),
    # 9. reasoning_tool_artifact
    ParityFixture(
        id="reasoning_tool_artifact",
        script=[
            _tt("reasoning", {"content": "let's search"}),
            _tt("tool_start", {"call_id": "c1", "tool": "search_kb", "args": {"q": "x"}}),
            _tt("tool_result", {"call_id": "c1", "result": {"hits": 1}, "status": "ok"}),
            _tt("artifact", {"type": "zettel", "action": "created", "zettel": {"id": 7}}),
            _tt("token", {"content": "done"}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={
            "content": "done",
            "reasoning_traces": "let's search",
            "tool_calls": [
                {
                    "call_id": "c1",
                    "tool": "search_kb",
                    "args": {"q": "x"},
                    "status": "ok",
                    "result": {"hits": 1},
                }
            ],
            "artifacts": [{"type": "zettel", "action": "created", "zettel": {"id": 7}}],
        },
    ),
    # 10. mid_stream_error
    ParityFixture(
        id="mid_stream_error",
        script=[
            _tt("token", {"content": "hello"}),
            _tt("token", {"content": " wor"}),
            _tt("error", {"error": "upstream timeout"}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={"content": "hello wor"},
    ),
    # 11. long_token_stream
    ParityFixture(
        id="long_token_stream",
        script=[_tt("token", {"content": "x"}) for _ in range(50)] + [_tt("done", {})],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={"content": "x" * 50},
    ),
    # 12. empty_run_no_persistence
    ParityFixture(
        id="empty_run_no_persistence",
        script=[_tt("done", {})],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected=None,  # sentinel: no row should be written
    ),
    # 13. tool_no_args
    ParityFixture(
        id="tool_no_args",
        script=[
            _tt("tool_start", {"call_id": "c1", "tool": "tick_clock", "args": {}}),
            _tt("tool_result", {"call_id": "c1", "result": {}, "status": "ok"}),
            _tt("token", {"content": "done"}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={
            "content": "done",
            "tool_calls": [
                {
                    "call_id": "c1",
                    "tool": "tick_clock",
                    "args": {},
                    "status": "ok",
                    "result": {},
                }
            ],
        },
    ),
    # 14. unicode_content
    ParityFixture(
        id="unicode_content",
        script=[
            _tt("token", {"content": "café ☕"}),
            _tt("token", {"content": " ñ"}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={"content": "café ☕ ñ"},
    ),
    # 15. zettel_found_artifact
    ParityFixture(
        id="zettel_found_artifact",
        script=[
            _tt("artifact", {"type": "zettel", "action": "found", "zettel": {"id": 11}}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={
            "content": "",
            "artifacts": [{"type": "zettel", "action": "found", "zettel": {"id": 11}}],
        },
    ),
    # 16. zettel_updated_artifact
    ParityFixture(
        id="zettel_updated_artifact",
        script=[
            _tt("artifact", {"type": "zettel", "action": "updated", "zettel": {"id": 22}}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={
            "content": "",
            "artifacts": [{"type": "zettel", "action": "updated", "zettel": {"id": 22}}],
        },
    ),
    # 17. interleaved_tools_and_artifacts
    ParityFixture(
        id="interleaved_tools_and_artifacts",
        script=[
            _tt("tool_start", {"call_id": "c1", "tool": "tool_a", "args": {"x": 1}}),
            _tt("tool_result", {"call_id": "c1", "result": {"y": 2}, "status": "ok"}),
            _tt("artifact", {"type": "zettel", "action": "created", "zettel": {"id": 10}}),
            _tt("tool_start", {"call_id": "c2", "tool": "tool_b", "args": {"z": 3}}),
            _tt("tool_result", {"call_id": "c2", "result": {"w": 4}, "status": "ok"}),
            _tt("artifact", {"type": "zettel", "action": "created", "zettel": {"id": 20}}),
            _tt("token", {"content": "ok"}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={
            "content": "ok",
            "tool_calls": [
                {
                    "call_id": "c1",
                    "tool": "tool_a",
                    "args": {"x": 1},
                    "status": "ok",
                    "result": {"y": 2},
                },
                {
                    "call_id": "c2",
                    "tool": "tool_b",
                    "args": {"z": 3},
                    "status": "ok",
                    "result": {"w": 4},
                },
            ],
            "artifacts": [
                {"type": "zettel", "action": "created", "zettel": {"id": 10}},
                {"type": "zettel", "action": "created", "zettel": {"id": 20}},
            ],
        },
    ),
    # 18. lens_research_model_o3
    ParityFixture(
        id="lens_research_model_o3",
        script=[
            _tt("token", {"content": "k"}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens="research",
        model="o3",
        expected={"content": "k"},
    ),
    # 19. empty_reasoning_skipped
    ParityFixture(
        id="empty_reasoning_skipped",
        script=[
            _tt("reasoning", {"content": ""}),
            _tt("token", {"content": "ok"}),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={"content": "ok", "reasoning_traces": None},
    ),
    # 20. tool_timeout_status
    ParityFixture(
        id="tool_timeout_status",
        script=[
            _tt("tool_start", {"call_id": "c1", "tool": "slow_tool", "args": {}}),
            _tt(
                "tool_result",
                {
                    "call_id": "c1",
                    "result": {"error": "timeout"},
                    "status": "timeout",
                },
            ),
            _tt("done", {}),
        ],
        thread_id=0,
        lens=None,
        model="gpt-5.4",
        expected={
            "content": "",
            "tool_calls": [
                {
                    "call_id": "c1",
                    "tool": "slow_tool",
                    "args": {},
                    "status": "timeout",
                    "result": {"error": "timeout"},
                }
            ],
        },
    ),
]
