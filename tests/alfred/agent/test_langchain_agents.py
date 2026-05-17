from __future__ import annotations

from types import SimpleNamespace

from alfred.services.agent.langchain_agents import create_alfred_agent, create_alfred_deep_agent
from alfred.services.agent.langchain_middleware import LangChainMiddlewareConfig


def test_create_alfred_agent_injects_global_middleware(monkeypatch) -> None:
    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(kind="agent")

    monkeypatch.setattr("langchain.agents.create_agent", fake_create_agent)

    result = create_alfred_agent(
        model="openai:gpt-4.1",
        tools=[],
        system_prompt="system",
        middleware_config=LangChainMiddlewareConfig(
            enable_summarization=False,
            enable_context_editing=False,
            enable_tool_selection=False,
        ),
    )

    assert result.kind == "agent"
    names = {type(item).__name__ for item in captured["middleware"]}
    assert "ModelRetryMiddleware" in names
    assert "ToolRetryMiddleware" in names
    assert "HumanInTheLoopMiddleware" in names


def test_create_alfred_deep_agent_injects_global_middleware(monkeypatch) -> None:
    captured = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(kind="deep_agent")

    import deepagents

    monkeypatch.setattr(deepagents, "create_deep_agent", fake_create_deep_agent)

    result = create_alfred_deep_agent(
        model="openai:gpt-4.1",
        tools=[],
        system_prompt="system",
        middleware_config=LangChainMiddlewareConfig(
            enable_summarization=False,
            enable_context_editing=False,
            enable_tool_selection=False,
        ),
    )

    assert result.kind == "deep_agent"
    names = {type(item).__name__ for item in captured["middleware"]}
    assert "ModelCallLimitMiddleware" in names
    assert "ToolCallLimitMiddleware" in names
    assert "TodoListMiddleware" in names
