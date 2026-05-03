"""MessageProjector — accumulates agent state and dual-writes AgentMessageRow.

Reads the typed RunEvent stream and produces an AgentMessageRow matching the
v1 persistence contract (see apps/alfred/api/agent/routes.py:_persist_message
and the frontend ToolCall TS type at web/lib/stores/agent-store.ts).

Phase 1 role: schema translator. The projector accumulates state internally
using v1 JSON key shape (``call_id``, ``tool``) so ``on_run_finished`` can
INSERT a row the existing frontend understands without further transformation.

Spec: docs/superpowers/specs/2026-05-01-streaming-revamp-design.md section 6.3
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from sqlmodel import Session

from alfred.streaming.events import (
    AnyRunEvent,
    MessageDelta,
    MessageStarted,
    RunFinished,
    RunStarted,
    StateDelta,
    ThinkingDelta,
    ToolResult,
    ToolStarted,
)
from alfred.streaming.projectors._parts import (
    finalize_streaming_parts,
    handle_reasoning,
    handle_token,
    handle_tool_result,
    handle_tool_start,
)


class MessageProjector:
    """Accumulate run state; dual-write an AgentMessageRow on terminal."""

    def __init__(self, session: Session | None) -> None:
        self.session = session
        self.content_parts: list[str] = []
        self.thinking_parts: list[str] = []
        # tool_calls[] entries use v1 legacy JSON key shape so the existing
        # frontend ToolCall TS type keeps working unmodified.
        self.tool_calls: list[dict[str, Any]] = []
        self.artifacts: list[dict[str, Any]] = []
        self.related_cards: list[dict[str, Any]] = []
        self.gaps: list[dict[str, Any]] = []
        # AI Elements canonical parts[] — dual-written alongside legacy fields.
        # Mirrors web/lib/stores/agent-store.ts parts construction.
        self.parts: list[dict[str, Any]] = []
        self._message_id: UUID | None = None
        self._thread_id: int | None = None
        self._active_lens: str | None = None
        self._model_id: str | None = None
        self._run_id: UUID | None = None

    def on_event(self, event: AnyRunEvent) -> None:
        now_ms = int(time.time() * 1000)
        if isinstance(event, RunStarted):
            self._thread_id = event.thread_id
            self._active_lens = event.active_lens
            self._model_id = event.model_id
            self._run_id = event.run_id
        elif isinstance(event, MessageStarted):
            self._message_id = event.message_id
        elif isinstance(event, MessageDelta):
            self.content_parts.append(event.delta_text)
            handle_token(self.parts, event.delta_text)
        elif isinstance(event, ThinkingDelta):
            self.thinking_parts.append(event.delta_text)
            handle_reasoning(self.parts, event.delta_text, now_ms)
        elif isinstance(event, ToolStarted):
            # v1 legacy key shape: call_id / tool / args / status
            self.tool_calls.append({
                "call_id": str(event.tool_call_id),
                "tool": event.tool_name,
                "args": dict(event.args_preview),
                "status": "pending",
            })
            handle_tool_start(
                self.parts,
                tool_name=event.tool_name,
                call_id=str(event.tool_call_id),
                args=dict(event.args_preview),
                now_ms=now_ms,
            )
        elif isinstance(event, ToolResult):
            target_id = str(event.tool_call_id)
            for tc in self.tool_calls:
                if tc.get("call_id") == target_id:
                    tc["status"] = event.status
                    tc["result"] = event.result_json
                    break
            handle_tool_result(
                self.parts,
                call_id=target_id,
                result=event.result_json,
                is_error=(event.status != "ok"),
            )
        elif isinstance(event, StateDelta):
            self._apply_state(event)

    def on_run_finished(self, terminal: AnyRunEvent) -> None:
        """Dual-write — INSERT an AgentMessageRow if we have content to persist."""
        if self.session is None or self._thread_id is None:
            return
        content_text = self.content
        # Match v1 skip predicate: write only if content OR tools OR artifacts present.
        if not content_text and not self.tool_calls and not self.artifacts:
            return
        # Close any still-streaming text/reasoning parts before persistence.
        finalize_streaming_parts(self.parts, int(time.time() * 1000))
        # Late import keeps projector importable without the models package loaded.
        from alfred.models.thinking import AgentMessageRow

        token_count = None
        if isinstance(terminal, RunFinished):
            token_count = terminal.tokens_out

        row = AgentMessageRow(
            thread_id=self._thread_id,
            role="assistant",
            content=content_text,
            reasoning_traces=self.thinking or None,
            tool_calls=self.tool_calls or None,
            artifacts=self.artifacts or None,
            related_cards=self.related_cards or None,
            gaps=self.gaps or None,
            parts=self.parts or None,
            active_lens=self._active_lens,
            model_used=self._model_id,
            token_count=token_count,
            run_id=self._run_id,
            projected_from_events=True,
        )
        self.session.add(row)
        self.session.commit()

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
