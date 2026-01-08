"""LangGraph-friendly tool execution utilities.

LangGraph versions used by this repo do not ship with the newer prebuilt tool
nodes/conditions, so we keep a small, explicit runtime that:
1) Detects tool calls on the last AI message.
2) Executes tool calls against a provided tool list.
3) Appends ToolMessage results back into the state.

This module is intentionally framework-light: it operates on plain dict states
with a `messages` list, making it easy to reuse across multiple graphs.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable, Mapping, MutableMapping

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool


def has_tool_calls(state: Mapping[str, Any], *, message_key: str = "messages") -> bool:
    """Return True if the last message contains tool calls."""

    msgs = state.get(message_key, [])
    if not isinstance(msgs, list) or not msgs:
        return False
    last = msgs[-1]
    return isinstance(last, AIMessage) and bool(getattr(last, "tool_calls", None))


def _tool_calls_from_message(message: AIMessage) -> list[dict[str, Any]]:
    calls = getattr(message, "tool_calls", None) or []
    normalized: list[dict[str, Any]] = []
    for call in calls:
        if isinstance(call, dict):
            name = call.get("name")
            args = call.get("args", {})
            call_id = call.get("id") or name
        else:
            name = getattr(call, "name", None)
            args = getattr(call, "args", None) or {}
            call_id = getattr(call, "id", None) or name
        if not name:
            continue
        normalized.append({"name": str(name), "args": args, "id": str(call_id or name)})
    return normalized


def _invoke_tool(tool: BaseTool, tool_input: Any) -> Any:
    """Invoke a tool robustly for mixed call shapes (dict, str, ToolCall)."""

    try:
        return tool.invoke(tool_input)
    except Exception:
        # Some community tools expect `.run(...)`.
        return tool.run(tool_input)


def _stringify_tool_result(result: Any) -> str:
    """Convert tool outputs to stable text for ToolMessage content.

    Prefer JSON for structured values so downstream LLM prompts can reliably parse
    them if needed.
    """

    if isinstance(result, (dict, list)):
        try:
            return json.dumps(result, ensure_ascii=False)
        except Exception:
            return str(result)
    return str(result)


def run_tool_calls(
    *,
    tools: Iterable[BaseTool],
    message: AIMessage,
    max_workers: int = 8,
) -> list[ToolMessage]:
    """Execute tool calls found on `message`, returning ToolMessages in call order."""

    tools_by_name = {t.name: t for t in tools}
    calls = _tool_calls_from_message(message)
    if not calls:
        return []

    work: list[tuple[int, BaseTool | None, Any, str, str]] = []
    for idx, call in enumerate(calls):
        name = call["name"]
        args = call.get("args", {})
        call_id = call.get("id") or name
        work.append((idx, tools_by_name.get(name), args, str(call_id), name))

    def _run_one(item: tuple[int, BaseTool | None, Any, str, str]) -> tuple[int, ToolMessage]:
        idx, tool, args, call_id, name = item
        if tool is None:
            return idx, ToolMessage(content=f"(tool not found: {name})", tool_call_id=call_id)
        try:
            result = _invoke_tool(tool, args)
        except Exception as exc:
            result = f"(error) {exc}"
        return idx, ToolMessage(content=_stringify_tool_result(result), tool_call_id=call_id)

    max_workers = max(1, min(int(max_workers), len(work)))
    if max_workers == 1 or len(work) == 1:
        out = [_run_one(item) for item in work]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            out = list(executor.map(_run_one, work))

    out.sort(key=lambda x: x[0])
    return [m for _, m in out]


def tools_node(
    state: MutableMapping[str, Any],
    *,
    tools: Iterable[BaseTool],
    message_key: str = "messages",
    max_workers: int = 8,
) -> dict[str, Any]:
    """A drop-in LangGraph node function that executes tool calls."""

    msgs = state.get(message_key, [])
    if not isinstance(msgs, list) or not msgs:
        return {message_key: msgs}

    last = msgs[-1]
    if not isinstance(last, AIMessage):
        return {message_key: msgs}

    tool_messages = run_tool_calls(tools=tools, message=last, max_workers=max_workers)
    return {message_key: [*msgs, *tool_messages]}
