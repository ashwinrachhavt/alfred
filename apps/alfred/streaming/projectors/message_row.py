"""MessageProjector — maintains a projection of the assistant message state.

Phase 0: skeleton accumulator. Phase 1 will insert AgentMessageRow in
on_run_finished (dual-write).

Spec: docs/superpowers/specs/2026-05-01-streaming-revamp-design.md section 6.3
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session

from alfred.streaming.events import (
    AnyRunEvent,
    MessageDelta,
    MessageStarted,
    StateDelta,
    ThinkingDelta,
    ToolResult,
    ToolStarted,
)


class MessageProjector:
    def __init__(self, session: Session | None) -> None:
        self.session = session
        self.content_parts: list[str] = []
        self.thinking_parts: list[str] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.artifacts: list[dict[str, Any]] = []
        self.related_cards: list[dict[str, Any]] = []
        self.gaps: list[dict[str, Any]] = []
        self._message_id = None

    def on_event(self, event: AnyRunEvent) -> None:
        if isinstance(event, MessageStarted):
            self._message_id = event.message_id
        elif isinstance(event, MessageDelta):
            self.content_parts.append(event.delta_text)
        elif isinstance(event, ThinkingDelta):
            self.thinking_parts.append(event.delta_text)
        elif isinstance(event, ToolStarted):
            self.tool_calls.append({
                "tool_call_id": str(event.tool_call_id),
                "tool_name": event.tool_name, "status": "pending",
                "args": event.args_preview,
            })
        elif isinstance(event, ToolResult):
            for tc in self.tool_calls:
                if tc["tool_call_id"] == str(event.tool_call_id):
                    tc["status"] = event.status
                    tc["result"] = event.result_json
                    tc["duration_ms"] = event.duration_ms
                    break
        elif isinstance(event, StateDelta):
            self._apply_state(event)

    def on_run_finished(self, terminal: AnyRunEvent) -> None:
        # Phase 1 will INSERT an AgentMessageRow here. Phase 0 is a no-op.
        return None

    @property
    def content(self) -> str:
        return "".join(self.content_parts)

    @property
    def thinking(self) -> str:
        return "".join(self.thinking_parts)

    def _apply_state(self, event: StateDelta) -> None:
        target = {
            "artifacts": self.artifacts,
            "related_cards": self.related_cards,
            "gaps": self.gaps,
        }.get(event.key)
        if target is None:
            return
        if event.op == "append":
            target.append(event.value)
        elif event.op == "set" and isinstance(event.value, list):
            target.clear()
            target.extend(event.value)


__all__ = ["MessageProjector"]
