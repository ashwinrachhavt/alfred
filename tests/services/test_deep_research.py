"""Unit tests for DeepResearchService and the tool registry."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from alfred.schemas.research_agent import ResearchAgentSpecCreate, SubAgentSpec
from alfred.services.deep_research import DeepResearchService, get_tool_registry


class FakeToken:
    """Minimal LangChain-like token shape used by _translate_chunk."""

    def __init__(self, content: str = "", tool_calls: list[dict] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls or []


async def _collect(gen: AsyncIterator[tuple[str, dict[str, Any], str]]) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    async for event_name, data, _sse_str in gen:
        out.append((event_name, data))
    return out


def _make_fake_agent(chunks: list[dict]) -> Any:
    """Build a fake compiled graph whose .astream yields the given chunks."""

    async def _astream(_inputs, **_kwargs):
        for c in chunks:
            yield c

    agent = MagicMock()
    agent.astream = _astream
    return agent


# -- Registry -------------------------------------------------------------


def test_registry_resolves_known_tools() -> None:
    reg = get_tool_registry()
    tools = reg.resolve(["search_web", "search_kb"])
    assert len(tools) == 2


def test_registry_raises_on_unknown_tool() -> None:
    reg = get_tool_registry()
    with pytest.raises(ValueError) as exc:
        reg.resolve(["does_not_exist"])
    assert "does_not_exist" in str(exc.value)


def test_registry_catalog_is_nonempty() -> None:
    reg = get_tool_registry()
    catalog = reg.catalog()
    assert len(catalog) >= 4
    names = {e.name for e in catalog}
    assert {"search_web", "search_papers", "search_kb", "scrape_url"} <= names


# -- Service translation --------------------------------------------------


@pytest.mark.asyncio
async def test_stream_run_emits_plan_event_once_per_change() -> None:
    """Todos emitted on every update chunk should only cause one plan event if unchanged."""
    db = MagicMock()
    svc = DeepResearchService(db)

    todos_v1 = [{"content": "task 1", "status": "pending"}]
    todos_v2 = [{"content": "task 1", "status": "in_progress"}]

    chunks: list[dict] = [
        {"type": "updates", "ns": [], "data": {"agent": {"todos": todos_v1}}},
        # Same todos -> no new plan event
        {"type": "updates", "ns": [], "data": {"agent": {"todos": todos_v1}}},
        {"type": "updates", "ns": [], "data": {"agent": {"todos": todos_v2}}},
    ]
    fake = _make_fake_agent(chunks)
    events = await _collect(svc.stream_run(agent=fake, topic="test"))

    plan_events = [e for e in events if e[0] == "plan"]
    assert len(plan_events) == 2, f"expected 2 plan events for 2 distinct states, got {plan_events}"


@pytest.mark.asyncio
async def test_stream_run_lanes_subagent_tokens() -> None:
    """Tokens in a `tools:<uuid>` namespace should emit subagent_msg decorated with the
    human subagent name (learned from msg.name on updates) rather than the UUID."""
    db = MagicMock()
    svc = DeepResearchService(db)

    named_msg = MagicMock()
    named_msg.name = "researcher"

    chunks = [
        # First an `updates` chunk teaches the service the UUID->name mapping.
        {
            "type": "updates",
            "ns": ["tools:uuid-123"],
            "data": {"model": {"messages": [named_msg]}},
        },
        # Now a `messages` chunk from the same namespace should be lane-tagged.
        {
            "type": "messages",
            "ns": ["tools:uuid-123"],
            "data": (FakeToken(content="sub output"), {}),
        },
        {
            "type": "messages",
            "ns": [],
            "data": (FakeToken(content="main output"), {}),
        },
    ]
    fake = _make_fake_agent(chunks)
    events = await _collect(svc.stream_run(agent=fake, topic="test"))

    sub_events = [e for e in events if e[0] == "subagent_msg"]
    main_events = [e for e in events if e[0] == "token"]
    assert len(sub_events) == 1
    assert sub_events[0][1]["subagent"] == "researcher"
    assert sub_events[0][1]["content"] == "sub output"
    assert len(main_events) == 1
    assert main_events[0][1]["content"] == "main output"


@pytest.mark.asyncio
async def test_stream_run_emits_file_write_and_done() -> None:
    db = MagicMock()
    svc = DeepResearchService(db)

    chunks = [
        {
            "type": "updates",
            "ns": [],
            "data": {"agent": {"files": {"/final_report.md": "Hello"}}},
        },
    ]
    fake = _make_fake_agent(chunks)
    events = await _collect(svc.stream_run(agent=fake, topic="test"))

    file_events = [e for e in events if e[0] == "file_write"]
    done_events = [e for e in events if e[0] == "done"]
    assert len(file_events) == 1
    assert file_events[0][1]["path"] == "/final_report.md"
    assert file_events[0][1]["bytes"] == len("Hello")
    assert len(done_events) == 1
    assert done_events[0][1]["final_files"] == {"/final_report.md": "Hello"}


@pytest.mark.asyncio
async def test_stream_run_emits_error_on_exception() -> None:
    db = MagicMock()
    svc = DeepResearchService(db)

    async def _boom(_inputs, **_kwargs):
        yield {"type": "updates", "ns": [], "data": {}}
        raise RuntimeError("boom")

    agent = MagicMock()
    agent.astream = _boom

    events = await _collect(svc.stream_run(agent=agent, topic="test"))
    errors = [e for e in events if e[0] == "error"]
    assert len(errors) == 1
    assert "boom" in errors[0][1]["message"]
