from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from alfred.services.agent.agent_types import AGENT_TYPES, AgentType
from alfred.services.agent.subagent import SubAgentRunner


def _choice(*, content: str = "", tool_calls: list | None = None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls or [],
                )
            )
        ]
    )


def _tool_call(name: str, args: str = "{}"):
    return SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name=name, arguments=args),
    )


@pytest.mark.asyncio
async def test_subagent_forces_final_synthesis_when_tool_budget_is_exhausted(monkeypatch):
    agent_type = AgentType(
        name="unit",
        description="Unit test agent",
        system_prompt="You are a test agent.",
        tool_names=["fake_tool"],
        max_iterations=1,
    )
    monkeypatch.setitem(AGENT_TYPES, "unit", agent_type)
    monkeypatch.setattr(
        "alfred.services.agent.subagent._get_tool_schemas_for_type",
        lambda _agent_type: [{"type": "function", "function": {"name": "fake_tool"}}],
    )

    async def fake_execute_tool(name, args, db):
        return {"tool": name, "args": args, "result": "evidence"}

    monkeypatch.setattr("alfred.services.agent.subagent.execute_tool", fake_execute_tool)

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(
                    side_effect=[
                        _choice(tool_calls=[_tool_call("fake_tool", '{"query": "market"}')]),
                        _choice(content="Final synthesis from gathered evidence."),
                    ]
                )
            )
        )
    )

    runner = SubAgentRunner(
        db=SimpleNamespace(),
        tool_session_factory=lambda: SimpleNamespace(close=lambda: None),
    )
    runner._client = client

    result = await runner.run(task="Research a market", agent_type_name="unit")

    assert result == "Final synthesis from gathered evidence."
    assert client.chat.completions.create.await_count == 2
    first_call_kwargs = client.chat.completions.create.await_args_list[0].kwargs
    assert first_call_kwargs["parallel_tool_calls"] is True
    final_call_kwargs = client.chat.completions.create.await_args_list[-1].kwargs
    assert "tools" not in final_call_kwargs
    assert "reached the tool-call budget" in final_call_kwargs["messages"][-1]["content"]
