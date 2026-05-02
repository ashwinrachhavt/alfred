"""AgentProducer — adapts AgentService.stream_turn to typed RunEvent stream.

The existing ``AgentService.stream_turn`` yields 3-tuples
``(event_name, data_dict, sse_str)``. This producer ignores ``sse_str`` (the
AG-UI wire frames come from ``AGUIProjector``) and maps ``event_name`` +
``data_dict`` to typed ``RunEvent`` instances.

Yielded events carry placeholder ``run_id`` (zero UUID) and ``seq=0``. The
caller is expected to pass each event to ``recorder.emit_raw(event)`` which
rewrites both fields. See ``RunRecorder.emit_raw`` for the rewrite contract.

Tool-call pairing invariant: the existing service uses opaque string
``call_id`` values. The producer maps each to a stable UUIDv4 the first
time it sees that string, so ``tool.started`` and ``tool.result`` for the
same call share a ``tool_call_id``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from alfred.streaming.events import (
    AnyRunEvent,
    MessageDelta,
    MessageStarted,
    RunErrored,
    StateDelta,
    ThinkingDelta,
    ToolResult,
    ToolStarted,
)

_PLACEHOLDER_RUN_ID: UUID = UUID("00000000-0000-0000-0000-000000000000")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class _AgentServiceProtocol(Protocol):
    """Minimal surface we need from AgentService — eases test doubles."""

    def stream_turn(self, **kwargs: Any) -> AsyncIterator[tuple[str, dict[str, Any], str]]:
        ...


class AgentProducer:
    """Async iterator yielding typed RunEvents derived from AgentService output."""

    def __init__(
        self,
        *,
        service: _AgentServiceProtocol,
        message: str,
        thread_id: int | None,
        model: str | None,
        lens: str | None,
        history: list | None = None,
        note_context: dict | None = None,
        intent: str | None = None,
        intent_args: dict | None = None,
        max_iterations: int | None = None,
    ) -> None:
        self.service = service
        self.message = message
        self.thread_id = thread_id
        self.model = model
        self.lens = lens
        self.history = history
        self.note_context = note_context
        self.intent = intent
        self.intent_args = intent_args
        self.max_iterations = max_iterations
        self._message_id: UUID | None = None

    def _ensure_message_id(self) -> UUID:
        if self._message_id is None:
            self._message_id = uuid4()
        return self._message_id

    async def stream(self) -> AsyncIterator[AnyRunEvent]:
        """Iterate AgentService output and yield typed RunEvents.

        seq / run_id are placeholders (0 / zero-UUID); the Recorder rewrites
        them via ``emit_raw``.
        """
        kwargs: dict[str, Any] = {
            "message": self.message,
            "thread_id": self.thread_id,
            "model": self.model,
            "lens": self.lens,
        }
        if self.history is not None:
            kwargs["history"] = self.history
        if self.note_context is not None:
            kwargs["note_context"] = self.note_context
        if self.intent is not None:
            kwargs["intent"] = self.intent
        if self.intent_args is not None:
            kwargs["intent_args"] = self.intent_args
        if self.max_iterations is not None:
            kwargs["max_iterations"] = self.max_iterations

        first_token_emitted = False

        async for event_name, data, _sse_str in self.service.stream_turn(**kwargs):
            if event_name == "token":
                if not first_token_emitted:
                    mid = self._ensure_message_id()
                    yield MessageStarted(
                        run_id=_PLACEHOLDER_RUN_ID, seq=0, emitted_at=_utcnow(),
                        message_id=mid,
                    )
                    first_token_emitted = True
                yield MessageDelta(
                    run_id=_PLACEHOLDER_RUN_ID, seq=0, emitted_at=_utcnow(),
                    message_id=self._ensure_message_id(),
                    delta_text=str(data.get("content", "")),
                )
            elif event_name == "reasoning":
                yield ThinkingDelta(
                    run_id=_PLACEHOLDER_RUN_ID, seq=0, emitted_at=_utcnow(),
                    message_id=self._ensure_message_id(),
                    delta_text=str(data.get("content", "")),
                )
            elif event_name == "tool_start":
                call_id = str(data.get("call_id", ""))
                yield ToolStarted(
                    run_id=_PLACEHOLDER_RUN_ID, seq=0, emitted_at=_utcnow(),
                    tool_call_id=call_id,
                    tool_name=str(data.get("tool", "unknown")),
                    args_preview=dict(data.get("args") or {}),
                )
            elif event_name == "tool_result":
                call_id = str(data.get("call_id", ""))
                status = str(data.get("status", "ok"))
                if status not in ("ok", "error", "timeout"):
                    status = "ok"
                yield ToolResult(
                    run_id=_PLACEHOLDER_RUN_ID, seq=0, emitted_at=_utcnow(),
                    tool_call_id=call_id,
                    result_json=dict(data.get("result") or {}),
                    duration_ms=int(data.get("duration_ms") or 0),
                    status=status,  # type: ignore[arg-type]
                )
            elif event_name == "artifact":
                yield StateDelta(
                    run_id=_PLACEHOLDER_RUN_ID, seq=0, emitted_at=_utcnow(),
                    key="artifacts", op="append", value=data,
                )
            elif event_name == "error":
                yield RunErrored(
                    run_id=_PLACEHOLDER_RUN_ID, seq=0, emitted_at=_utcnow(),
                    error_type="AgentError",
                    error_message=str(data.get("message", "")),
                )
                return
            elif event_name == "done":
                return


__all__ = ["AgentProducer"]
