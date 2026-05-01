"""Tests for DigestAgent (LLM-backed) and CarryoverAgent (deterministic).

LLM calls are mocked via monkeypatching ``get_chat_model`` in the agent
module so no network traffic happens. Registry is cleared per-test.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from alfred.models.doc_storage import DocumentRow  # noqa: F401 - metadata registration
from alfred.models.today import DailyEntryRow
from alfred.models.zettel import ZettelCard, ZettelReview  # noqa: F401 - metadata registration
from alfred.services.today.agents.carryover_agent import CarryoverAgent
from alfred.services.today.agents.digest_agent import DigestAgent
from alfred.services.today.pipeline import DailyContext, DailyPipeline


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def _clean_registry():
    DailyPipeline.clear_registry()
    yield
    DailyPipeline.clear_registry()


def _today() -> date:
    return date(2026, 4, 30)


def _make_ctx(
    *,
    entries: list[DailyEntryRow] | None = None,
    zettels: list[dict[str, Any]] | None = None,
    captures: list[dict[str, Any]] | None = None,
    reviews_completed: list[dict[str, Any]] | None = None,
    user_id: str | None = None,
) -> DailyContext:
    return DailyContext(
        entry_date=_today(),
        tz_name="UTC",
        user_id=user_id,
        run_id="abcdef012345",
        entries=list(entries or []),
        zettels_created=list(zettels or []),
        captures=list(captures or []),
        reviews_due=[],
        reviews_completed=list(reviews_completed or []),
    )


@dataclass
class _FakeResponse:
    content: Any


class _FakeModel:
    """Minimal stand-in for a LangChain chat model."""

    def __init__(self, *, content: Any = "- Summary bullet", raises: Exception | None = None):
        self._content = content
        self._raises = raises
        self.calls: list[Any] = []

    def invoke(self, messages: Any) -> _FakeResponse:
        self.calls.append(messages)
        if self._raises is not None:
            raise self._raises
        return _FakeResponse(content=self._content)


# DigestAgent tests


def test_digest_agent_happy_path(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeModel(content="- Summary bullet")
    monkeypatch.setattr(
        "alfred.services.today.agents.digest_agent.get_chat_model",
        lambda: fake,
    )

    ctx = _make_ctx(
        entries=[DailyEntryRow(entry_date=_today(), kind="todo", title="Ship it", status="done")]
    )
    agent = DigestAgent(session=db_session)

    ctx = agent.run(ctx)

    assert ctx.artifacts["digest_md"] == "- Summary bullet"
    assert "digest_error" not in ctx.artifacts
    assert len(fake.calls) == 1


def test_digest_agent_catches_llm_failure(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom() -> Any:
        raise RuntimeError("LLM down")

    monkeypatch.setattr(
        "alfred.services.today.agents.digest_agent.get_chat_model",
        _boom,
    )

    ctx = _make_ctx(entries=[])
    agent = DigestAgent(session=db_session)

    ctx = agent.run(ctx)

    assert ctx.artifacts["digest_md"] == ""
    assert "LLM down" in ctx.artifacts["digest_error"]


def test_digest_agent_builds_prompt_with_entries_and_artifacts(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeModel(content="- ok")
    monkeypatch.setattr(
        "alfred.services.today.agents.digest_agent.get_chat_model",
        lambda: fake,
    )

    entries = [
        DailyEntryRow(entry_date=_today(), kind="todo", title="Task A", status="done"),
        DailyEntryRow(entry_date=_today(), kind="todo", title="Task B", status="open"),
        DailyEntryRow(entry_date=_today(), kind="note", title="Note A"),
        DailyEntryRow(entry_date=_today(), kind="learning", title="Learning A"),
    ]
    zettels = [
        {
            "title": "Z1",
            "is_synthetic": True,
            "meta": {"ref_kind": "zettel"},
        }
    ]
    ctx = _make_ctx(entries=entries, zettels=zettels)

    DigestAgent(session=db_session).run(ctx)

    assert len(fake.calls) == 1
    user_content = next(m["content"] for m in fake.calls[0] if m["role"] == "user")

    assert _today().isoformat() in user_content
    assert "[x] Task A" in user_content
    assert "[ ] Task B" in user_content
    assert "Z1" in user_content
    assert "Notes:" in user_content
    assert "Learnings:" in user_content


# CarryoverAgent tests


def _insert_todo(
    session: Session,
    *,
    entry_date: date,
    title: str,
    status: str = "open",
    user_id: str | None = None,
    priority: int = 0,
    tags: list[str] | None = None,
) -> DailyEntryRow:
    row = DailyEntryRow(
        user_id=user_id,
        entry_date=entry_date,
        kind="todo",
        title=title,
        status=status,
        priority=priority,
        tags=list(tags or []),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_carryover_agent_moves_open_and_doing_todos(db_session: Session) -> None:
    today = _today()
    tomorrow = today + timedelta(days=1)

    open_todo = _insert_todo(db_session, entry_date=today, title="Open T", status="open")
    doing_todo = _insert_todo(db_session, entry_date=today, title="Doing T", status="doing")
    done_todo = _insert_todo(db_session, entry_date=today, title="Done T", status="done")
    note = DailyEntryRow(entry_date=today, kind="note", title="A note")
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)

    entries = list(
        db_session.exec(select(DailyEntryRow).where(DailyEntryRow.entry_date == today)).all()
    )
    ctx = _make_ctx(entries=entries)

    CarryoverAgent(session=db_session).run(ctx)

    tomorrow_rows = list(
        db_session.exec(select(DailyEntryRow).where(DailyEntryRow.entry_date == tomorrow)).all()
    )
    assert len(tomorrow_rows) == 2

    sources = {(r.meta or {}).get("source_entry_id") for r in tomorrow_rows}
    assert sources == {open_todo.id, doing_todo.id}

    assert done_todo.id not in sources
    assert note.id not in sources

    for row in tomorrow_rows:
        assert row.kind == "todo"
        assert row.status == "open"
        assert row.meta.get("carried_from") == today.isoformat()


def test_carryover_agent_is_idempotent(db_session: Session) -> None:
    today = _today()
    tomorrow = today + timedelta(days=1)

    _insert_todo(db_session, entry_date=today, title="T1", status="open")
    _insert_todo(db_session, entry_date=today, title="T2", status="doing")

    def _run() -> None:
        entries = list(
            db_session.exec(select(DailyEntryRow).where(DailyEntryRow.entry_date == today)).all()
        )
        ctx = _make_ctx(entries=entries)
        CarryoverAgent(session=db_session).run(ctx)

    _run()
    first_count = len(
        db_session.exec(select(DailyEntryRow).where(DailyEntryRow.entry_date == tomorrow)).all()
    )
    assert first_count == 2

    _run()
    second_count = len(
        db_session.exec(select(DailyEntryRow).where(DailyEntryRow.entry_date == tomorrow)).all()
    )
    assert second_count == 2


def test_carryover_agent_writes_count_to_artifacts(db_session: Session) -> None:
    today = _today()
    _insert_todo(db_session, entry_date=today, title="T1", status="open")
    _insert_todo(db_session, entry_date=today, title="T2", status="open")
    _insert_todo(db_session, entry_date=today, title="T3", status="doing")

    entries = list(
        db_session.exec(select(DailyEntryRow).where(DailyEntryRow.entry_date == today)).all()
    )
    ctx = _make_ctx(entries=entries)

    CarryoverAgent(session=db_session).run(ctx)

    assert ctx.artifacts["carryover_count"] == 3


# Registry auto-population


def test_agents_package_import_populates_registry() -> None:
    DailyPipeline.clear_registry()

    import alfred.services.today.agents as agents_pkg
    import alfred.services.today.agents.carryover_agent as carryover_mod
    import alfred.services.today.agents.digest_agent as digest_mod

    importlib.reload(digest_mod)
    importlib.reload(carryover_mod)
    importlib.reload(agents_pkg)

    reflect_agents = DailyPipeline.registered_agents("reflect")
    prep_agents = DailyPipeline.registered_agents("prep")

    assert any(cls.__name__ == "DigestAgent" for cls in reflect_agents)
    assert any(cls.__name__ == "CarryoverAgent" for cls in prep_agents)
