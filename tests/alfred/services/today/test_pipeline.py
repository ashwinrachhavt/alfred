from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from alfred.models.doc_storage import DocumentRow  # noqa: F401 — metadata registration
from alfred.models.today import DailyEntryRow, DailyReflectionRow
from alfred.models.zettel import ZettelCard, ZettelReview  # noqa: F401
from alfred.services.today.pipeline import (
    STAGE_ORDER,
    DailyContext,
    DailyPipeline,
)
from alfred.services.today.reflection_service import ReflectionService


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def _clean_registry():
    """Every test starts with an empty registry and leaves it empty."""
    DailyPipeline.clear_registry()
    yield
    DailyPipeline.clear_registry()


def _today() -> date:
    return date(2026, 4, 30)


# ---------------------------------------------------------------------------
# Registry behavior
# ---------------------------------------------------------------------------


def test_register_adds_agent_class_to_stage() -> None:
    @DailyPipeline.register(stage="reflect")
    class MyAgent:
        def __init__(self, *, session: Session) -> None:
            self.session = session

        def run(self, ctx: DailyContext) -> DailyContext:
            return ctx

    assert MyAgent in DailyPipeline.registered_agents("reflect")
    assert DailyPipeline.registered_agents("enrich") == []


def test_register_rejects_unknown_stage() -> None:
    with pytest.raises(ValueError, match="unknown stage"):

        @DailyPipeline.register(stage="harvest")  # intentionally not in STAGE_ORDER
        class _Bad:
            pass


def test_clear_registry_empties_all_stages() -> None:
    @DailyPipeline.register(stage="enrich")
    class _A:
        pass

    @DailyPipeline.register(stage="prep")
    class _B:
        pass

    DailyPipeline.clear_registry()
    for stage in STAGE_ORDER:
        assert DailyPipeline.registered_agents(stage) == []


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------


def test_pipeline_runs_stages_in_order(db_session: Session) -> None:
    call_log: list[str] = []

    def _make(name: str):
        class _Agent:
            def __init__(self, *, session: Session) -> None:
                self.session = session

            def run(self, ctx: DailyContext) -> DailyContext:
                call_log.append(name)
                return ctx

        _Agent.__name__ = name
        return _Agent

    DailyPipeline.register(stage="enrich")(_make("EnrichAgent"))
    DailyPipeline.register(stage="connect")(_make("ConnectAgent"))
    DailyPipeline.register(stage="reflect")(_make("ReflectAgent"))
    DailyPipeline.register(stage="prep")(_make("PrepAgent"))

    DailyPipeline().run(
        session=db_session,
        entry_date=_today(),
        tz_name="UTC",
        user_id=None,
    )

    assert call_log == ["EnrichAgent", "ConnectAgent", "ReflectAgent", "PrepAgent"]


def test_agent_exception_does_not_abort_pipeline(db_session: Session) -> None:
    second_ran = {"flag": False}

    @DailyPipeline.register(stage="reflect")
    class BoomAgent:
        def __init__(self, *, session: Session) -> None: ...

        def run(self, ctx: DailyContext) -> DailyContext:
            raise RuntimeError("boom")

    @DailyPipeline.register(stage="reflect")
    class OKAgent:
        def __init__(self, *, session: Session) -> None: ...

        def run(self, ctx: DailyContext) -> DailyContext:
            second_ran["flag"] = True
            return ctx

    reflection = DailyPipeline().run(
        session=db_session,
        entry_date=_today(),
        tz_name="UTC",
        user_id=None,
    )

    assert second_ran["flag"] is True, "second agent must run after first failed"
    # Error captured in the reflection stats so it's observable post-run.
    assert "errors" in reflection.stats
    errors = reflection.stats["errors"]
    assert any(e.get("agent") == "BoomAgent" and e.get("stage") == "reflect" for e in errors)


# ---------------------------------------------------------------------------
# DailyContext.harvest
# ---------------------------------------------------------------------------


def test_harvest_loads_entries_for_the_date_only(db_session: Session) -> None:
    today = _today()
    yesterday = date(2026, 4, 29)

    db_session.add(DailyEntryRow(entry_date=today, kind="todo", title="A"))
    db_session.add(DailyEntryRow(entry_date=today, kind="note", title="B"))
    db_session.add(DailyEntryRow(entry_date=yesterday, kind="todo", title="C"))
    db_session.commit()

    ctx = DailyContext.harvest(session=db_session, entry_date=today, tz_name="UTC", user_id=None)

    titles = sorted(e.title for e in ctx.entries)
    assert titles == ["A", "B"]
    assert ctx.entry_date == today
    assert ctx.tz_name == "UTC"
    assert len(ctx.run_id) == 12  # uuid4 hex[:12]


# ---------------------------------------------------------------------------
# ReflectionService idempotency
# ---------------------------------------------------------------------------


def test_reflection_upsert_creates_on_first_call(db_session: Session) -> None:
    db_session.add(DailyEntryRow(entry_date=_today(), kind="todo", title="T", status="done"))
    db_session.add(DailyEntryRow(entry_date=_today(), kind="note", title="N"))
    db_session.commit()

    ctx = DailyContext.harvest(session=db_session, entry_date=_today(), tz_name="UTC", user_id=None)
    ctx.artifacts["digest_md"] = "first run"

    row = ReflectionService(session=db_session).upsert_for_date(
        ctx=ctx, stages_ran=list(STAGE_ORDER)
    )

    assert row.digest_md == "first run"
    assert row.stats["version"] == 1
    assert row.stats["entry_counts"]["todo"] == 1
    assert row.stats["entry_counts"]["todo_done"] == 1
    assert row.stats["entry_counts"]["note"] == 1
    assert row.stages_ran == list(STAGE_ORDER)


def test_reflection_upsert_updates_on_second_call(db_session: Session) -> None:
    ctx1 = DailyContext.harvest(
        session=db_session, entry_date=_today(), tz_name="UTC", user_id=None
    )
    ctx1.artifacts["digest_md"] = "v1"
    svc = ReflectionService(session=db_session)
    row1 = svc.upsert_for_date(ctx=ctx1, stages_ran=["reflect"])

    ctx2 = DailyContext.harvest(
        session=db_session, entry_date=_today(), tz_name="UTC", user_id=None
    )
    ctx2.artifacts["digest_md"] = "v2"
    row2 = svc.upsert_for_date(ctx=ctx2, stages_ran=["reflect", "prep"])

    # Same row id — idempotent upsert, not insert.
    assert row1.id == row2.id
    # Content reflects the second run.
    assert row2.digest_md == "v2"
    assert row2.stages_ran == ["reflect", "prep"]
    # Only one reflection row for this date.
    rows = db_session.exec(
        select(DailyReflectionRow).where(DailyReflectionRow.entry_date == _today())
    ).all()
    assert len(rows) == 1


def test_pipeline_end_to_end_produces_reflection(db_session: Session) -> None:
    db_session.add(DailyEntryRow(entry_date=_today(), kind="todo", title="A"))
    db_session.add(DailyEntryRow(entry_date=_today(), kind="learning", title="L"))
    db_session.commit()

    @DailyPipeline.register(stage="reflect")
    class Hello:
        def __init__(self, *, session: Session) -> None: ...

        def run(self, ctx: DailyContext) -> DailyContext:
            ctx.artifacts["digest_md"] = "hello"
            return ctx

    reflection = DailyPipeline().run(
        session=db_session,
        entry_date=_today(),
        tz_name="UTC",
        user_id=None,
    )

    assert reflection.digest_md == "hello"
    assert reflection.stats["entry_counts"]["todo"] == 1
    assert reflection.stats["entry_counts"]["learning"] == 1
    assert "reflect" in reflection.stages_ran
