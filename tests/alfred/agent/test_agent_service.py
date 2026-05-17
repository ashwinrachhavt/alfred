from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from alfred.services.agent.service import AgentService


class _FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_stream_turn_executes_same_turn_tool_calls_concurrently(monkeypatch) -> None:
    sessions: list[_FakeSession] = []

    def session_factory() -> _FakeSession:
        session = _FakeSession()
        sessions.append(session)
        return session

    async def fake_execute_tool(name: str, args: dict[str, Any], db: _FakeSession) -> dict[str, Any]:
        await asyncio.sleep(0.1)
        return {"name": name, "value": args["value"], "db_id": id(db)}

    monkeypatch.setattr("alfred.services.agent.service.execute_tool", fake_execute_tool)

    service = AgentService(SimpleNamespace(), tool_session_factory=session_factory)
    monkeypatch.setattr(service, "_build_api_kwargs", lambda _model, _messages: {})

    calls = 0

    async def fake_stream_tokens(
        _kwargs: dict[str, Any],
        _is_disconnected=None,
    ) -> AsyncIterator[dict[str, Any]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            yield {
                "type": "tool_calls",
                "tool_calls": [
                    {"call_id": "call_1", "name": "slow_tool", "args": {"value": 1}},
                    {"call_id": "call_2", "name": "slow_tool", "args": {"value": 2}},
                ],
            }

    monkeypatch.setattr(service, "_stream_tokens", fake_stream_tokens)

    started = time.perf_counter()
    events = [event async for event in service.stream_turn(message="run tools")]
    elapsed = time.perf_counter() - started

    tool_results = [data for event_name, data, _ in events if event_name == "tool_result"]
    done_events = [data for event_name, data, _ in events if event_name == "done"]

    assert elapsed < 0.3
    assert {result["call_id"] for result in tool_results} == {"call_1", "call_2"}
    assert len(sessions) == 2
    assert all(session.closed for session in sessions)
    assert done_events[-1]["tool_calls"] is not None
    assert done_events[-1]["run_id"].startswith("run_")
    assert any(event["type"] == "tool.completed" for event in done_events[-1]["trace_events"])


def test_build_api_kwargs_enables_openai_parallel_tool_calls(monkeypatch) -> None:
    monkeypatch.setattr("alfred.services.agent.service.get_all_tool_schemas", lambda: [])

    service = AgentService(SimpleNamespace())
    kwargs = service._build_api_kwargs("gpt-4.1", [])

    assert kwargs["parallel_tool_calls"] is True
