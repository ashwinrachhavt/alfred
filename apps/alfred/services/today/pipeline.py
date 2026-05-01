"""Pluggable nightly pipeline for the Today page.

Stages run in order: enrich, connect, reflect, prep. Agents register via
``@DailyPipeline.register(stage=...)``. Harvesting (loading entries / zettels /
captures / reviews for the date) is done inline in ``DailyContext.harvest``,
so there is no separate harvest stage at PoC.

See ``alfred.services.today.agents.__init__`` for the explicit agent imports
that populate the registry at module-load time.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, ClassVar, Protocol

from sqlmodel import Session, select

from alfred.models.today import DailyEntryRow, DailyReflectionRow

STAGE_ORDER: tuple[str, ...] = ("enrich", "connect", "reflect", "prep")


class DailyAgent(Protocol):
    """Pipeline agent protocol — every registered class must be instantiable
    with ``session=...`` and expose a ``.run(ctx)`` that returns the mutated
    ``DailyContext``."""

    def __init__(self, *, session: Session) -> None: ...

    def run(self, ctx: DailyContext) -> DailyContext: ...


@dataclass
class DailyContext:
    """Shared mutable state that agents read from and write to.

    ``artifacts`` is the freeform output bag — the reflect stage writes
    ``digest_md`` here, the connect stage can write link counts, etc. The
    :class:`ReflectionService` reads this at the end to build the
    :class:`DailyReflectionRow`.
    """

    entry_date: date
    tz_name: str
    user_id: str | None
    run_id: str
    entries: list[DailyEntryRow]
    # Typed as ``list[Any]`` to avoid circular imports against domain models
    # (zettels / documents / reviews) in this low-level module.
    zettels_created: list[Any]
    captures: list[Any]
    reviews_due: list[Any]
    reviews_completed: list[Any]
    artifacts: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def harvest(
        cls,
        *,
        session: Session,
        entry_date: date,
        tz_name: str,
        user_id: str | None,
    ) -> DailyContext:
        """Load the day's rows from the DB. This is where 'harvest' happens.

        Reuses :class:`EntryService`'s tz-local artifact synthesis so we do
        not duplicate the cross-table queries. Any source-side failure is
        recorded in ``ctx.errors`` without aborting the harvest.
        """
        # Inline import to avoid circulars at module load.
        from alfred.services.today.entry_service import EntryService

        svc = EntryService(session=session)

        # 1. DailyEntryRow for the date (tz-local semantics live in the
        #    EntryService call below; the entries table stores dates, so an
        #    equality filter is correct here).
        entries_stmt = select(DailyEntryRow).where(DailyEntryRow.entry_date == entry_date)
        if user_id is not None:
            entries_stmt = entries_stmt.where(DailyEntryRow.user_id == user_id)
        entries = list(session.exec(entries_stmt).all())

        ctx = cls(
            entry_date=entry_date,
            tz_name=tz_name,
            user_id=user_id,
            run_id=uuid.uuid4().hex[:12],
            entries=entries,
            zettels_created=[],
            captures=[],
            reviews_due=[],
            reviews_completed=[],
        )

        # 2. Delegate the cross-table (zettel / capture / review) fetch to
        #    the existing service so tz-handling stays in one place. The
        #    service returns synthetic ``artifact_ref`` dicts carrying
        #    ``meta.ref_kind``.
        try:
            page = svc.list_entries(
                start=entry_date,
                end=entry_date,
                tz_name=tz_name,
                include_artifacts=True,
                user_id=user_id,
                limit=1000,
            )
            for item in page.entries:
                if not item.get("is_synthetic"):
                    continue
                ref_kind = (item.get("meta") or {}).get("ref_kind")
                if ref_kind == "zettel":
                    ctx.zettels_created.append(item)
                elif ref_kind == "capture":
                    ctx.captures.append(item)
                elif ref_kind == "review":
                    ctx.reviews_completed.append(item)
        except Exception as error:  # pragma: no cover - defensive
            ctx.errors.append({"stage": "harvest", "error": str(error)})

        return ctx


class DailyPipeline:
    """Pluggable pipeline with a class-based stage registry.

    Agents register via ``@DailyPipeline.register(stage="reflect")``. The
    registry holds agent *classes*; they are instantiated per-run with the
    session. Each agent runs its stage; exceptions are caught, logged into
    ``ctx.errors``, and the pipeline continues on to the next agent / stage.
    """

    _registry: ClassVar[defaultdict[str, list[type]]] = defaultdict(list)

    @classmethod
    def register(cls, *, stage: str) -> Callable[[type], type]:
        if stage not in STAGE_ORDER:
            raise ValueError(f"unknown stage {stage!r}; must be one of {STAGE_ORDER}")

        def decorator(agent_cls: type) -> type:
            cls._registry[stage].append(agent_cls)
            return agent_cls

        return decorator

    @classmethod
    def clear_registry(cls) -> None:
        """Test helper — reset the registry between unit tests."""
        cls._registry = defaultdict(list)

    @classmethod
    def registered_agents(cls, stage: str) -> list[type]:
        """Introspection helper for tests and debugging."""
        return list(cls._registry.get(stage, []))

    def run(
        self,
        *,
        session: Session,
        entry_date: date,
        tz_name: str,
        user_id: str | None = None,
    ) -> DailyReflectionRow:
        """Execute the full pipeline and persist a :class:`DailyReflectionRow`.

        Agent exceptions are caught per-agent so a single failure does not
        abort the whole run. Pipeline-level exceptions (harvest failure,
        reflection persist) propagate.
        """
        # Ensure agents are imported (populates registry via decorators).
        # The agents package is a placeholder in T10 and will be populated
        # with real agent modules in T11.
        import alfred.services.today.agents  # noqa: F401

        ctx = DailyContext.harvest(
            session=session,
            entry_date=entry_date,
            tz_name=tz_name,
            user_id=user_id,
        )

        stages_ran: list[str] = []
        for stage in STAGE_ORDER:
            for agent_cls in type(self)._registry.get(stage, []):
                try:
                    agent = agent_cls(session=session)
                    ctx = agent.run(ctx)
                except Exception as error:
                    ctx.errors.append(
                        {
                            "stage": stage,
                            "agent": agent_cls.__name__,
                            "error": str(error),
                        }
                    )
            stages_ran.append(stage)

        # Inline import to avoid an import cycle at module load time.
        from alfred.services.today.reflection_service import ReflectionService

        return ReflectionService(session=session).upsert_for_date(ctx=ctx, stages_ran=stages_ran)


__all__ = ["STAGE_ORDER", "DailyAgent", "DailyContext", "DailyPipeline"]
