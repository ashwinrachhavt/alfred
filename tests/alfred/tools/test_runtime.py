from __future__ import annotations

from alfred.agents.utils.runtime import has_tool_calls, tools_node
from alfred.agents.utils.web_tools import make_web_search_tool
from langchain_core.messages import AIMessage, ToolMessage


def test_tools_node_executes_structured_tool_calls(monkeypatch):
    # Tool implementation: deterministic and no network.
    def _search_web(*, q: str, searx_k: int = 5, **_kwargs):
        return {"provider": "searx", "query": q, "hits": [{"title": "T", "url": "u"}], "meta": {}}

    tool = make_web_search_tool(search_web=_search_web)

    msg = AIMessage(
        content="",
        tool_calls=[{"name": "web_search", "args": {"q": "hello"}, "id": "call-1"}],
    )
    state = {"messages": [msg]}

    assert has_tool_calls(state)

    out = tools_node(state, tools=[tool])
    assert "messages" in out
    assert isinstance(out["messages"][-1], ToolMessage)
    assert '"query": "hello"' in out["messages"][-1].content


def test_tools_node_reports_missing_tool():
    msg = AIMessage(
        content="",
        tool_calls=[{"name": "missing", "args": {"q": "hello"}, "id": "call-1"}],
    )
    out = tools_node({"messages": [msg]}, tools=[])
    last = out["messages"][-1]
    assert isinstance(last, ToolMessage)
    assert "tool not found" in last.content
