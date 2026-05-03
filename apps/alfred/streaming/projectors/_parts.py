"""Shared parts[] accumulator helpers used by both v1 SSE routes and the
v2 MessageProjector. Mirrors the frontend agent-store.ts parts construction.

Keep in sync with `web/lib/stores/agent-store.ts` _handleSSEEvent + the
_appendToStreamingText / _appendToStreamingReasoning / _finalizeStreamingParts
helpers there. The parts[] shape is the AI Elements canonical format:

  {type: "text",       text, state}                              # streaming|done
  {type: "reasoning",  text, state, startedAt, finishedAt?}       # streaming|done
  {type: "tool-<name>", toolCallId, state, input, output?, errorText?}
                                                                  # input-available|output-available|output-error
"""

from __future__ import annotations

import time
from typing import Any


def _now_ms() -> int:
    return int(time.time() * 1000)


def handle_token(parts: list[dict[str, Any]], delta: str) -> None:
    """Append streaming text — either extend trailing streaming text part or start one."""
    if not delta:
        return
    if parts and parts[-1].get("type") == "text" and parts[-1].get("state") == "streaming":
        parts[-1]["text"] = parts[-1].get("text", "") + delta
    else:
        parts.append({"type": "text", "text": delta, "state": "streaming"})


def handle_reasoning(parts: list[dict[str, Any]], delta: str, now_ms: int | None = None) -> None:
    """Append streaming reasoning — extend trailing streaming reasoning or start one."""
    if not delta:
        return
    ts = now_ms if now_ms is not None else _now_ms()
    if parts and parts[-1].get("type") == "reasoning" and parts[-1].get("state") == "streaming":
        parts[-1]["text"] = parts[-1].get("text", "") + delta
    else:
        parts.append({
            "type": "reasoning",
            "text": delta,
            "state": "streaming",
            "startedAt": ts,
        })


def handle_tool_start(
    parts: list[dict[str, Any]],
    *,
    tool_name: str,
    call_id: str,
    args: dict[str, Any] | None,
    now_ms: int | None = None,
) -> None:
    """Finalize any open streaming parts, then append a tool part in input-available state."""
    ts = now_ms if now_ms is not None else _now_ms()
    finalize_streaming_parts(parts, ts)
    parts.append({
        "type": f"tool-{tool_name}",
        "toolCallId": call_id or "",
        "state": "input-available",
        "input": dict(args or {}),
    })


def handle_tool_result(
    parts: list[dict[str, Any]],
    *,
    call_id: str,
    result: Any,
    is_error: bool | None = None,
) -> None:
    """Update the matching tool part to output-available or output-error.

    If ``is_error`` is None, auto-detect: a dict result with a truthy "error" key
    is treated as an error (mirrors the frontend).
    """
    if is_error is None:
        is_error = isinstance(result, dict) and bool(result.get("error"))
    for part in reversed(parts):
        type_str = str(part.get("type", ""))
        if not type_str.startswith("tool-"):
            continue
        if call_id and part.get("toolCallId") == call_id:
            pass  # matched by id
        elif not call_id and part.get("state") == "input-available":
            pass  # legacy no-id fallback (matches frontend behavior)
        else:
            continue
        if is_error:
            part["state"] = "output-error"
            if isinstance(result, dict):
                part["errorText"] = str(result.get("error"))
            else:
                part["errorText"] = str(result) if result is not None else ""
        else:
            part["state"] = "output-available"
            part["output"] = result
        break


def handle_error(
    parts: list[dict[str, Any]],
    message: str,
    now_ms: int | None = None,
) -> None:
    """Finalize streaming parts, then append a done text part with the error message."""
    ts = now_ms if now_ms is not None else _now_ms()
    finalize_streaming_parts(parts, ts)
    parts.append({
        "type": "text",
        "text": message or "Something went wrong.",
        "state": "done",
    })


def finalize_streaming_parts(parts: list[dict[str, Any]], now_ms: int | None = None) -> None:
    """Transition any trailing streaming text/reasoning parts to done.

    Reasoning parts additionally get ``finishedAt`` stamped.
    """
    ts = now_ms if now_ms is not None else _now_ms()
    for part in parts:
        if part.get("type") == "text" and part.get("state") == "streaming":
            part["state"] = "done"
        elif part.get("type") == "reasoning" and part.get("state") == "streaming":
            part["state"] = "done"
            part["finishedAt"] = ts


__all__ = [
    "handle_token",
    "handle_reasoning",
    "handle_tool_start",
    "handle_tool_result",
    "handle_error",
    "finalize_streaming_parts",
]
