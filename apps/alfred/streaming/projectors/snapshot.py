"""SnapshotProjector — writes agent_run_snapshots rows.

Cadence: every 100 events and at every terminal event.

Spec: docs/superpowers/specs/2026-05-01-streaming-revamp-design.md sections 5.3 + 6.3
"""

from __future__ import annotations

import logging

from sqlmodel import Session

from alfred.models.streaming import AgentRunSnapshotRow
from alfred.streaming.events import AnyRunEvent, MessageDelta, ThinkingDelta

logger = logging.getLogger(__name__)

_SNAPSHOT_CADENCE = 100


class SnapshotProjector:
    def __init__(self, session: Session | None) -> None:
        self.session = session
        self._event_count = 0
        self._message_text_parts: list[str] = []
        self._thinking_text_parts: list[str] = []
        self._last_run_id = None
        self._last_seq = 0

    def on_event(self, event: AnyRunEvent) -> None:
        self._event_count += 1
        self._last_run_id = event.run_id
        self._last_seq = event.seq
        if isinstance(event, MessageDelta):
            self._message_text_parts.append(event.delta_text)
        elif isinstance(event, ThinkingDelta):
            self._thinking_text_parts.append(event.delta_text)
        if self._event_count % _SNAPSHOT_CADENCE == 0:
            self._write_snapshot()

    def on_run_finished(self, terminal: AnyRunEvent) -> None:
        self._last_run_id = terminal.run_id
        self._last_seq = terminal.seq
        self._write_snapshot()

    def _write_snapshot(self) -> None:
        if self.session is None or self._last_run_id is None:
            return
        try:
            row = AgentRunSnapshotRow(
                run_id=self._last_run_id,
                up_to_seq=self._last_seq,
                state={},
                message_text="".join(self._message_text_parts),
                thinking_text="".join(self._thinking_text_parts),
                tokens_so_far=0,
            )
            self.session.add(row)
            self.session.commit()
        except Exception:
            logger.exception("snapshot write failed")
            self.session.rollback()


__all__ = ["SnapshotProjector"]
