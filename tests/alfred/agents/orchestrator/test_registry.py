"""Tests for ToolRegistry."""

from __future__ import annotations

import pytest
from langchain_core.tools import tool

from alfred.agents.orchestrator.registry import ToolRegistry


@tool
def echo_tool(text: str) -> str:
    """Echo the input text back."""
    return f"echo: {text}"


@tool
def add_tool(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def test_register_and_list_tools():
    registry = ToolRegistry()
    registry.register(echo_tool)
    registry.register(add_tool)
    assert len(registry.tools) == 2
    assert "echo_tool" in registry.tools
    assert "add_tool" in registry.tools


def test_get_lc_tools_returns_list():
    registry = ToolRegistry()
    registry.register(echo_tool)
    lc_tools = registry.get_lc_tools()
    assert len(lc_tools) == 1
    assert lc_tools[0].name == "echo_tool"


def test_execute_known_tool():
    registry = ToolRegistry()
    registry.register(echo_tool)
    result = registry.execute("echo_tool", {"text": "hello"})
    assert result == "echo: hello"


def test_execute_unknown_tool_raises():
    registry = ToolRegistry()
    with pytest.raises(KeyError, match="not_a_tool"):
        registry.execute("not_a_tool", {})


def test_duplicate_register_overwrites():
    registry = ToolRegistry()
    registry.register(echo_tool)
    registry.register(echo_tool)
    assert len(registry.tools) == 1
