"""AGUIProjector — translates RunEvents into AG-UI wire frame dicts.

Phase 0 scope: one frame per event per the mapping in spec section 7.2.
Phase 1 will serialize frames into SSE byte strings.

Spec: docs/superpowers/specs/2026-05-01-streaming-revamp-design.md section 7
"""

from __future__ import annotations

import json
from typing import Any

from alfred.streaming.events import (
    AnyRunEvent,
    ApprovalRequired,
    ApprovalResolved,
    MessageDelta,
    MessageFinished,
    MessageStarted,
    ProgressUpdate,
    RunCancelled,
    RunErrored,
    RunFinished,
    RunStarted,
    StateDelta,
    StateSnapshot,
    ThinkingDelta,
    ThinkingFinished,
    ToolArgsDelta,
    ToolArgsFinished,
    ToolResult,
    ToolStarted,
)


class AGUIProjector:
    def on_event(self, event: AnyRunEvent) -> None:
        return None

    def on_run_finished(self, terminal: AnyRunEvent) -> None:
        return None

    def frames_for(self, event: AnyRunEvent) -> list[dict[str, Any]]:
        if isinstance(event, RunStarted):
            return [{
                "type": "RUN_STARTED",
                "runId": str(event.run_id),
                "threadId": str(event.thread_id) if event.thread_id is not None else None,
                "parentRunId": str(event.parent_run_id) if event.parent_run_id else None,
                "runType": event.run_type,
            }]
        if isinstance(event, RunFinished):
            return [{"type": "RUN_FINISHED", "runId": str(event.run_id), "result": {
                "durationMs": event.duration_ms,
                "tokensIn": event.tokens_in,
                "tokensOut": event.tokens_out,
            }}]
        if isinstance(event, RunErrored):
            return [{"type": "RUN_ERROR",
                "message": event.error_message,
                "code": event.error_type,
            }]
        if isinstance(event, RunCancelled):
            return [{"type": "RUN_FINISHED", "runId": str(event.run_id), "result": {
                "status": "cancelled",
                "reason": event.reason,
            }}]
        if isinstance(event, MessageStarted):
            return [{"type": "TEXT_MESSAGE_START",
                "messageId": str(event.message_id),
                "role": event.role,
            }]
        if isinstance(event, MessageDelta):
            return [{"type": "TEXT_MESSAGE_CONTENT",
                "messageId": str(event.message_id),
                "delta": event.delta_text,
            }]
        if isinstance(event, MessageFinished):
            return [{"type": "TEXT_MESSAGE_END", "messageId": str(event.message_id)}]
        if isinstance(event, ThinkingDelta):
            return [{"type": "REASONING_MESSAGE_CONTENT",
                "messageId": f"{event.message_id}::reasoning",
                "delta": event.delta_text,
            }]
        if isinstance(event, ThinkingFinished):
            return [{"type": "REASONING_MESSAGE_END", "messageId": f"{event.message_id}::reasoning"}]
        if isinstance(event, ToolStarted):
            frames: list[dict[str, Any]] = [{
                "type": "TOOL_CALL_START",
                "toolCallId": str(event.tool_call_id),
                "toolCallName": event.tool_name,
                "parentMessageId": str(event.parent_message_id) if event.parent_message_id else None,
            }]
            if event.args_preview:
                frames.append({
                    "type": "TOOL_CALL_ARGS",
                    "toolCallId": str(event.tool_call_id),
                    "delta": json.dumps(event.args_preview, separators=(",", ":"), default=str),
                })
            frames.append({
                "type": "TOOL_CALL_END",
                "toolCallId": str(event.tool_call_id),
            })
            return frames
        if isinstance(event, ToolArgsDelta):
            return [{"type": "TOOL_CALL_ARGS",
                "toolCallId": str(event.tool_call_id),
                "delta": event.delta_json,
            }]
        if isinstance(event, ToolArgsFinished):
            return [{"type": "TOOL_CALL_END", "toolCallId": str(event.tool_call_id)}]
        if isinstance(event, ToolResult):
            message_id = getattr(event, "message_id", None)
            return [{"type": "TOOL_CALL_RESULT",
                "messageId": str(message_id) if message_id else f"{event.tool_call_id}::result",
                "toolCallId": str(event.tool_call_id),
                "role": "tool",
                "content": json.dumps(event.result_json, separators=(",", ":"), default=str),
            }]
        if isinstance(event, StateDelta):
            return [{"type": "STATE_DELTA", "delta": [_state_patch_for(event)]}]
        if isinstance(event, StateSnapshot):
            return [{"type": "STATE_SNAPSHOT", "snapshot": _camel_state(event.state)}]
        if isinstance(event, ProgressUpdate):
            return [{"type": "CUSTOM", "name": "alfred.progress", "value": {
                "stage": event.stage,
                "message": event.message,
                "pctComplete": event.pct_complete,
            }}]
        if isinstance(event, ApprovalRequired):
            return [{"type": "CUSTOM",
                "name": "alfred.approval_required",
                "value": {
                    "approvalId": str(event.approval_id),
                    "action": event.action,
                    "payload": event.payload,
                    "reason": event.reason,
                },
            }]
        if isinstance(event, ApprovalResolved):
            return [{"type": "CUSTOM",
                "name": "alfred.approval_resolved",
                "value": {
                    "approvalId": str(event.approval_id),
                    "decision": event.decision,
                    "resolvedBy": event.resolved_by,
                },
            }]
        return []


def _camel_state(state: dict[str, Any]) -> dict[str, Any]:
    return {_state_key(k): v for k, v in state.items()}


def _state_key(key: str) -> str:
    aliases = {
        "related_cards": "relatedCards",
        "pending_approvals": "pendingApprovals",
        "reasoning_summary": "reasoningSummary",
    }
    if key in aliases:
        return aliases[key]
    parts = key.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def _state_patch_for(event: StateDelta) -> dict[str, Any]:
    path = f"/{_state_key(event.key)}"
    if event.op == "append":
        return {"op": "add", "path": f"{path}/-", "value": event.value}
    if event.op in ("set", "merge"):
        return {"op": "add", "path": path, "value": event.value}
    if event.op == "remove":
        return {"op": "remove", "path": path}
    return {"op": "add", "path": path, "value": event.value}


__all__ = ["AGUIProjector"]
