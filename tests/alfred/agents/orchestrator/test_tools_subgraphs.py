"""Tests for SubGraphTool — wraps compiled LangGraph sub-graphs as tools."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from alfred.agents.orchestrator.tools.subgraphs import SubGraphTool


class _SimpleState(TypedDict):
    input: str
    output: str


def _build_echo_graph():
    def echo_node(state: _SimpleState) -> _SimpleState:
        return {"output": f"echoed: {state['input']}"}

    g = StateGraph(_SimpleState)
    g.add_node("echo", echo_node)
    g.add_edge(START, "echo")
    g.add_edge("echo", END)
    return g.compile()


def test_subgraph_tool_invoke():
    graph = _build_echo_graph()
    tool = SubGraphTool(
        graph=graph,
        name="echo_graph",
        description="Echoes input.",
        input_mapper=lambda args: {"input": args["query"], "output": ""},
        output_mapper=lambda result: result["output"],
    )
    result = tool.invoke({"query": "hello"})
    assert result == "echoed: hello"


def test_subgraph_tool_name_and_description():
    graph = _build_echo_graph()
    tool = SubGraphTool(
        graph=graph,
        name="my_tool",
        description="Does things.",
        input_mapper=lambda args: {"input": args.get("query", ""), "output": ""},
        output_mapper=lambda result: result.get("output", ""),
    )
    assert tool.name == "my_tool"
    assert tool.description == "Does things."


def test_subgraph_tool_error_handling():
    def failing_node(state: _SimpleState) -> _SimpleState:
        raise ValueError("intentional failure")

    g = StateGraph(_SimpleState)
    g.add_node("fail", failing_node)
    g.add_edge(START, "fail")
    g.add_edge("fail", END)
    graph = g.compile()

    tool = SubGraphTool(
        graph=graph,
        name="failing_tool",
        description="Always fails.",
        input_mapper=lambda args: {"input": "", "output": ""},
        output_mapper=lambda result: result.get("output", ""),
    )
    result = tool.invoke({"query": "test"})
    assert "error" in result.lower()
