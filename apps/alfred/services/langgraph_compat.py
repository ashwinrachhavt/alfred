from __future__ import annotations

import json
import warnings
from typing import Any, Dict, Iterable, Mapping, Sequence

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END

try:  # pragma: no cover - prefer official implementation when available
    from langgraph.prebuilt import ToolNode as _ToolNode  # type: ignore
    from langgraph.prebuilt import tools_condition as _tools_condition  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - runtime fallback
    warnings.warn(
        "langgraph.prebuilt.ToolNode unavailable (missing optional modules). "
        "Using lightweight compatibility shim; advanced agent features may be reduced.",
        RuntimeWarning,
    )

    class ToolNode:  # minimal shim covering registered BaseTool execution
        def __init__(self, tools: Sequence[BaseTool]) -> None:
            self._tools: Dict[str, BaseTool] = {tool.name: tool for tool in tools}

        @staticmethod
        def _serialize_output(output: Any) -> str | list[dict[str, Any]]:
            if isinstance(output, str):
                return output
            if isinstance(output, list) and all(isinstance(x, dict) for x in output):
                return output  # structured content block
            try:
                return json.dumps(output, ensure_ascii=False)
            except Exception:
                return str(output)

        @staticmethod
        def _coerce_tool_input(payload: Any) -> Any:
            if isinstance(payload, Mapping):
                if "input" in payload and len(payload) == 1:
                    return payload["input"]
                if len(payload) == 1:
                    return next(iter(payload.values()))
            return payload

        def __call__(self, state: Mapping[str, Any]) -> Dict[str, Sequence[ToolMessage]]:
            messages: Sequence[Any] = state.get("messages", [])  # type: ignore[assignment]
            if not messages:
                return {"messages": []}

            last = messages[-1]
            if isinstance(last, dict):  # graceful degradation if state mutated
                tool_calls: Iterable[Mapping[str, Any]] = last.get("tool_calls", [])
            elif isinstance(last, AIMessage):
                tool_calls = getattr(last, "tool_calls", []) or []
            else:
                tool_calls = getattr(last, "tool_calls", []) or []

            tool_messages: list[ToolMessage] = []
            for call in tool_calls:
                name = call.get("name") if isinstance(call, Mapping) else None
                tool_id = call.get("id") if isinstance(call, Mapping) else None
                args = call.get("args") if isinstance(call, Mapping) else None

                tool = self._tools.get(name or "")
                if tool is None:
                    content = f"Error: requested tool '{name}' is not available."
                else:
                    input_payload = self._coerce_tool_input(args)
                    try:
                        content = tool.invoke(input_payload)
                    except Exception:
                        try:
                            content = tool.run(input_payload)
                        except Exception as tool_exc:
                            content = f"(error) tool '{name}' failed: {tool_exc}"
                serialized = self._serialize_output(content)
                tool_messages.append(
                    ToolMessage(content=serialized, tool_call_id=str(tool_id or name or ""))
                )

            return {"messages": tool_messages}

    def tools_condition(state: Mapping[str, Any]) -> object:
        messages: Sequence[Any] = state.get("messages", [])  # type: ignore[assignment]
        if not messages:
            return END
        last = messages[-1]
        tool_calls = getattr(last, "tool_calls", None)
        if isinstance(last, dict):
            tool_calls = last.get("tool_calls")
        return "tools" if tool_calls else END

else:  # pragma: no cover
    ToolNode = _ToolNode
    tools_condition = _tools_condition

__all__ = ["ToolNode", "tools_condition"]
