"""RunRecorder — owns one run's lifecycle.

Responsibilities per emit:
  1. Assign monotonic seq (local counter).
  2. Append to in-memory buffer.
  3. Fan out to attached consumers (synchronous).
  4. Flush buffer on:
       - Significant event (not message.delta / thinking.delta / tool.args.delta)
       - Time budget (250ms)
       - Size budget (32 events)
       - Terminal event (run.finished / run.errored / run.cancelled)

DB write failures are logged but do NOT block the wire. Conscious asymmetry.

Spec: docs/superpowers/specs/2026-05-01-streaming-revamp-design.md section 6.1
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, Self
from uuid import UUID, uuid4

from sqlmodel import Session

from alfred.models.streaming import AgentRunEventRow, AgentRunRow
from alfred.streaming.consumers import EventConsumer
from alfred.streaming.events import (
    AnyRunEvent,
    MessageDelta,
    MessageStarted,
    RunErrored,
    RunFinished,
    RunStarted,
    ToolStarted,
)

logger = logging.getLogger(__name__)

_DELTA_TYPES = frozenset({"message.delta", "thinking.delta", "tool.args.delta"})
_FLUSH_INTERVAL_SECONDS = 0.25
_FLUSH_SIZE = 32


class RunRecorder:
    """One per run. Constructed via ``start``; closed via async context manager."""

    def __init__(
        self,
        session: Session,
        *,
        run_id: UUID,
        run_type: str,
        parent: RunRecorder | None = None,
        thread_id: int | None = None,
        model_id: str | None = None,
        active_lens: str | None = None,
    ) -> None:
        self.session = session
        self.run_id = run_id
        self.run_type = run_type
        self.parent = parent
        self.thread_id = thread_id
        self.model_id = model_id
        self.active_lens = active_lens
        self._seq = 0
        self._buffer: list[AnyRunEvent] = []
        self._last_flush_at = time.monotonic()
        self._consumers: list[EventConsumer] = []
        self._closed = False
        self._all_events: list[AnyRunEvent] = []  # Full history for replay on attach

    @classmethod
    def start(
        cls,
        session: Session,
        *,
        run_type: str,
        parent: RunRecorder | None = None,
        thread_id: int | None = None,
        model_id: str | None = None,
        active_lens: str | None = None,
        input_summary: str | None = None,
        user_id: str | None = None,
    ) -> Self:
        run_id = uuid4()
        row = AgentRunRow(
            id=run_id,
            parent_run_id=parent.run_id if parent else None,
            thread_id=thread_id,
            run_type=run_type,
            status="running",
            user_id=user_id,
            input_summary=input_summary,
            model_id=model_id,
            active_lens=active_lens,
        )
        session.add(row)
        session.commit()

        rec = cls(
            session, run_id=run_id, run_type=run_type, parent=parent,
            thread_id=thread_id, model_id=model_id, active_lens=active_lens,
        )
        started = RunStarted(
            run_id=run_id, seq=rec._next_seq(), emitted_at=_utcnow(),
            parent_run_id=parent.run_id if parent else None,
            run_type=run_type, thread_id=thread_id,
            user_id=user_id, input_summary=input_summary,
            model_id=model_id, active_lens=active_lens,
        )
        rec._record(started)
        rec._flush()
        return rec

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if self._closed:
            return False
        if exc is not None:
            self._emit_terminal(RunErrored(
                run_id=self.run_id, seq=self._next_seq(), emitted_at=_utcnow(),
                error_type=exc_type.__name__ if exc_type else "UnknownError",
                error_message=str(exc),
            ))
            return False
        self._emit_terminal(RunFinished(
            run_id=self.run_id, seq=self._next_seq(), emitted_at=_utcnow(),
        ))
        return False

    async def aclose(self) -> None:
        if self._closed:
            return
        self._emit_terminal(RunFinished(
            run_id=self.run_id, seq=self._next_seq(), emitted_at=_utcnow(),
        ))

    def attach(self, consumer: EventConsumer) -> None:
        # Replay all historical events to the new consumer
        for event in self._all_events:
            try:
                consumer.on_event(event)
            except Exception:
                logger.exception("consumer.on_event failed during replay")
        self._consumers.append(consumer)

    @property
    def recorded_events(self) -> tuple[AnyRunEvent, ...]:
        """Events recorded so far, including lifecycle events.

        Routes use this to send recorder-owned lifecycle events (run.started
        and terminal events) through the same wire projector as producer
        events.
        """
        return tuple(self._all_events)

    async def emit_message_started(self, *, message_id: UUID) -> MessageStarted:
        evt = MessageStarted(
            run_id=self.run_id, seq=self._next_seq(), emitted_at=_utcnow(),
            message_id=message_id,
        )
        self._record(evt)
        return evt

    async def emit_delta(self, *, message_id: UUID, delta_text: str) -> MessageDelta:
        evt = MessageDelta(
            run_id=self.run_id, seq=self._next_seq(), emitted_at=_utcnow(),
            message_id=message_id, delta_text=delta_text,
        )
        self._record(evt)
        return evt

    async def emit_tool_started(
        self, *, tool_call_id: str, tool_name: str,
        args_preview: dict[str, Any] | None = None,
        parent_message_id: UUID | None = None,
    ) -> ToolStarted:
        evt = ToolStarted(
            run_id=self.run_id, seq=self._next_seq(), emitted_at=_utcnow(),
            tool_call_id=tool_call_id, tool_name=tool_name,
            parent_message_id=parent_message_id, args_preview=args_preview or {},
        )
        self._record(evt)
        return evt

    async def emit_raw(self, event: AnyRunEvent) -> AnyRunEvent:
        """Escape hatch for producers emitting fully-formed events.

        Seq and run_id are rewritten to this recorder; emitted_at is preserved
        (events are frozen Pydantic models with emitted_at always set at construction).
        """
        stamped = event.model_copy(update={
            "seq": self._next_seq(),
            "run_id": self.run_id,
        })
        self._record(stamped)
        return stamped

    def _next_seq(self) -> int:
        s = self._seq
        self._seq += 1
        return s

    def _record(self, event: AnyRunEvent) -> None:
        self._buffer.append(event)
        self._all_events.append(event)  # Keep full history
        for c in self._consumers:
            try:
                c.on_event(event)
            except Exception:
                logger.exception("consumer.on_event failed; continuing")
        if self._should_flush(event):
            self._flush()

    def _should_flush(self, event: AnyRunEvent) -> bool:
        if event.event_type not in _DELTA_TYPES:
            return True
        if len(self._buffer) >= _FLUSH_SIZE:
            return True
        if (time.monotonic() - self._last_flush_at) >= _FLUSH_INTERVAL_SECONDS:
            return True
        return False

    def _flush(self) -> None:
        if not self._buffer:
            return
        rows = [
            AgentRunEventRow(
                id=None,
                run_id=e.run_id, seq=e.seq, event_type=e.event_type,
                payload=e.model_dump(mode="json"),
                emitted_at=e.emitted_at,
            )
            for e in self._buffer
        ]
        try:
            self.session.add_all(rows)
            self.session.commit()
        except Exception:
            logger.exception("event flush failed; dropping %d events", len(rows))
            self.session.rollback()
        self._buffer.clear()
        self._last_flush_at = time.monotonic()

    def _emit_terminal(self, event: AnyRunEvent) -> None:
        self._buffer.append(event)
        self._all_events.append(event)
        for c in self._consumers:
            try:
                c.on_event(event)
                c.on_run_finished(event)
            except Exception:
                logger.exception("consumer terminal fan-out failed")
        self._flush()
        run = self.session.get(AgentRunRow, self.run_id)
        if run is not None:
            run.finished_at = _utcnow()
            run.status = {
                "run.finished": "finished",
                "run.errored": "errored",
                "run.cancelled": "cancelled",
            }.get(event.event_type, "finished")
            if event.event_type == "run.errored":
                run.error_type = getattr(event, "error_type", None)
                run.error_message = getattr(event, "error_message", None)
            if event.event_type == "run.finished":
                run.duration_ms = getattr(event, "duration_ms", None)
                run.tokens_in = getattr(event, "tokens_in", None)
                run.tokens_out = getattr(event, "tokens_out", None)
            self.session.add(run)
            self.session.commit()
        self._closed = True


def _utcnow() -> datetime:
    return datetime.now(UTC)


__all__ = ["RunRecorder"]
