"""ReplayEngine — load events for a run and yield them in seq order.

Phase 0: bare loader. Phase 5 adds snapshot fast-forward, AG-UI projection,
and speed-controlled playback.

Spec: docs/superpowers/specs/2026-05-01-streaming-revamp-design.md section 6.5
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from pydantic import TypeAdapter
from sqlmodel import Session, select

from alfred.models.streaming import AgentRunEventRow
from alfred.streaming.events import AnyRunEvent

_adapter = TypeAdapter(AnyRunEvent)


class ReplayEngine:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def replay(
        self,
        run_id: UUID,
        target_seq: int | None = None,
    ) -> AsyncIterator[AnyRunEvent]:
        stmt = (
            select(AgentRunEventRow)
            .where(AgentRunEventRow.run_id == run_id)
            .order_by(AgentRunEventRow.seq)
        )
        if target_seq is not None:
            stmt = stmt.where(AgentRunEventRow.seq <= target_seq)
        rows = self.session.exec(stmt).all()
        for row in rows:
            yield _adapter.validate_python(row.payload)


__all__ = ["ReplayEngine"]
