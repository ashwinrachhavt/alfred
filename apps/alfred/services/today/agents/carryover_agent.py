"""Prep-stage agent that carries open todos forward to the next day.

Scope (kept tight for PoC):

- For every :class:`DailyEntryRow` with ``kind == 'todo'`` and
  ``status`` in ``{'open', 'doing'}`` on ``ctx.entry_date``, insert a new
  :class:`DailyEntryRow` for ``ctx.entry_date + 1 day`` with the same
  ``title`` / ``body_md`` / ``tags`` / ``priority`` and
  ``meta.source_entry_id`` pointing back at the original.
- Idempotent via a dedup key: ``(entry_date, kind='todo', meta.source_entry_id)``.
  If a row for tomorrow already references the same source, skip it.
- Does NOT carry notes, learnings, or artifact_refs - those are not
  work-items in flight.
- Writes the carry-over count to ``ctx.artifacts["carryover_count"]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlmodel import Session, select

from alfred.models.today import DailyEntryRow
from alfred.services.today.pipeline import DailyContext, DailyPipeline

_IN_FLIGHT_STATUSES: frozenset[str] = frozenset({"open", "doing"})


@DailyPipeline.register(stage="prep")
@dataclass
class CarryoverAgent:
    """Prep-stage agent: carries open/doing todos forward to tomorrow.

    Instantiated per-run by :class:`DailyPipeline` via
    ``CarryoverAgent(session=...)``.
    """

    session: Session

    def run(self, ctx: DailyContext) -> DailyContext:
        try:
            tomorrow = ctx.entry_date + timedelta(days=1)
            in_flight = [
                entry
                for entry in ctx.entries
                if entry.kind == "todo" and entry.status in _IN_FLIGHT_STATUSES
            ]

            if not in_flight:
                ctx.artifacts["carryover_count"] = 0
                return ctx

            # Load existing tomorrow rows once, check meta.source_entry_id for dedup.
            existing_stmt = select(DailyEntryRow).where(
                DailyEntryRow.entry_date == tomorrow,
                DailyEntryRow.kind == "todo",
            )
            if ctx.user_id is not None:
                existing_stmt = existing_stmt.where(DailyEntryRow.user_id == ctx.user_id)
            existing = self.session.exec(existing_stmt).all()

            already_sourced: set[int] = set()
            for row in existing:
                src = (row.meta or {}).get("source_entry_id")
                if isinstance(src, int):
                    already_sourced.add(src)

            created = 0
            for todo in in_flight:
                if todo.id is None:
                    continue
                if todo.id in already_sourced:
                    continue
                carried = DailyEntryRow(
                    user_id=todo.user_id,
                    entry_date=tomorrow,
                    kind="todo",
                    title=todo.title,
                    body_md=todo.body_md,
                    status="open",  # reset to open on carry-over (fresh slate)
                    priority=todo.priority,
                    tags=list(todo.tags or []),
                    meta={
                        "source_entry_id": todo.id,
                        "carried_from": ctx.entry_date.isoformat(),
                    },
                )
                self.session.add(carried)
                created += 1

            if created:
                self.session.commit()
            ctx.artifacts["carryover_count"] = created
        except Exception as error:
            ctx.artifacts.setdefault("carryover_error", str(error))
            ctx.artifacts.setdefault("carryover_count", 0)
        return ctx


__all__ = ["CarryoverAgent"]
