"""AGUIProjector — translates RunEvents into AG-UI wire frame dicts.

Phase 0 scope: one frame per event per the mapping in spec section 7.2.
Phase 1 will serialize frames into SSE byte strings.

Spec: docs/superpowers/specs/2026-05-01-streaming-revamp-design.md section 7
"""

from __future__ import annotations

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
            name = "RUN_STARTED" if event.parent_run_id is None else "STEP_STARTED"
            return [{
                "event": name,
                "data": {
                    "run_id": str(event.run_id),
                    "parent_run_id": str(event.parent_run_id) if event.parent_run_id else None,
                    "run_type": event.run_type,
                    "thread_id": event.thread_id,
                },
            }]
        if isinstance(event, RunFinished):
            return [{"event": "RUN_FINISHED", "data": {
                "run_id": str(event.run_id),
                "duration_ms": event.duration_ms,
                "tokens_in": event.tokens_in,
                "tokens_out": event.tokens_out,
            }}]
        if isinstance(event, RunErrored):
            return [{"event": "RUN_ERROR", "data": {
                "run_id": str(event.run_id),
                "error_type": event.error_type,
                "error_message": event.error_message,
            }}]
        if isinstance(event, RunCancelled):
            return [{"event": "RUN_FINISHED", "data": {
                "run_id": str(event.run_id),
                "status": "cancelled",
                "reason": event.reason,
            }}]
        if isinstance(event, MessageStarted):
            return [{"event": "TEXT_MESSAGE_START", "data": {
                "message_id": str(event.message_id),
                "role": event.role,
            }}]
        if isinstance(event, MessageDelta):
            return [{"event": "TEXT_MESSAGE_CHUNK", "data": {
                "message_id": str(event.message_id),
                "delta": event.delta_text,
            }}]
        if isinstance(event, MessageFinished):
            return [{"event": "TEXT_MESSAGE_END", "data": {
                "message_id": str(event.message_id),
            }}]
        if isinstance(event, ThinkingDelta):
            return [{"event": "TEXT_MESSAGE_CHUNK", "data": {
                "message_id": f"{event.message_id}::thinking",
                "delta": event.delta_text,
                "channel": "thinking",
            }}]
        if isinstance(event, ThinkingFinished):
            return [{"event": "TEXT_MESSAGE_END", "data": {
                "message_id": f"{event.message_id}::thinking",
            }}]
        if isinstance(event, ToolStarted):
            return [{"event": "TOOL_CALL_START", "data": {
                "tool_call_id": str(event.tool_call_id),
                "tool_name": event.tool_name,
                "parent_message_id": str(event.parent_message_id) if event.parent_message_id else None,
            }}]
        if isinstance(event, ToolArgsDelta):
            return [{"event": "TOOL_CALL_ARGS", "data": {
                "tool_call_id": str(event.tool_call_id),
                "delta": event.delta_json,
            }}]
        if isinstance(event, ToolArgsFinished):
            return [{"event": "TOOL_CALL_END", "data": {
                "tool_call_id": str(event.tool_call_id),
            }}]
        if isinstance(event, ToolResult):
            return [{"event": "TOOL_CALL_RESULT", "data": {
                "tool_call_id": str(event.tool_call_id),
                "role": "tool",
                "content": event.result_json,
                "status": event.status,
            }}]
        if isinstance(event, StateDelta):
            return [{"event": "STATE_DELTA", "data": {
                "key": event.key, "op": event.op, "value": event.value,
            }}]
        if isinstance(event, StateSnapshot):
            return [{"event": "STATE_SNAPSHOT", "data": {"state": event.state}}]
        if isinstance(event, ProgressUpdate):
            return [{"event": "CUSTOM", "data": {
                "name": "alfred.progress", "stage": event.stage,
                "message": event.message, "pct_complete": event.pct_complete,
            }}]
        if isinstance(event, ApprovalRequired):
            return [{"event": "CUSTOM", "data": {
                "name": "alfred.approval_required",
                "approval_id": str(event.approval_id),
                "action": event.action, "payload": event.payload, "reason": event.reason,
            }}]
        if isinstance(event, ApprovalResolved):
            return [{"event": "CUSTOM", "data": {
                "name": "alfred.approval_resolved",
                "approval_id": str(event.approval_id),
                "decision": event.decision, "resolved_by": event.resolved_by,
            }}]
        return []


__all__ = ["AGUIProjector"]
