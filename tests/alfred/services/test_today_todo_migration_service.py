from datetime import date

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.models.tasks import TaskRow
from alfred.models.today import DailyEntryRow
from alfred.services.tasks.today_migration_service import TodayTodoMigrationService
from alfred.services.today.entry_service import EntryService


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _todo(session: Session, *, title: str = "Legacy todo", status: str = "open") -> DailyEntryRow:
    row = DailyEntryRow(entry_date=date(2026, 5, 17), kind="todo", title=title, status=status, priority=1, tags=[])
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_migration_creates_task_and_stores_legacy_ref() -> None:
    session = _session()
    row = _todo(session)

    result = TodayTodoMigrationService(session).migrate(user_id="user_1")

    assert result.created == 1
    task = session.get(TaskRow, result.rows[0]["task_id"])
    assert task is not None
    assert task.legacy_today_entry_id == row.id
    session.refresh(row)
    assert row.meta["task_id"] == task.id


def test_migration_skips_existing_legacy_ref_without_duplicate() -> None:
    session = _session()
    row = _todo(session)
    service = TodayTodoMigrationService(session)

    first = service.migrate(user_id="user_1")
    second = service.migrate(user_id="user_1")

    assert first.created == 1
    assert second.duplicates == 1
    assert len(session.query(TaskRow).all()) == 1
    assert second.rows[0]["entry_id"] == row.id


def test_migration_ignores_deleted_entries() -> None:
    session = _session()
    row = _todo(session)
    session.delete(row)
    session.commit()

    result = TodayTodoMigrationService(session).migrate(user_id="user_1")

    assert result.created == 0
    assert result.skipped == 0
    assert result.duplicates == 0


def test_migration_reports_empty_titles_as_invalid() -> None:
    session = _session()
    _todo(session, title="   ")

    result = TodayTodoMigrationService(session).migrate(user_id="user_1")

    assert result.invalid == 1
    assert result.rows[0]["action"] == "invalid"
    assert len(session.query(TaskRow).all()) == 0


def test_dry_run_reports_would_create_without_writing() -> None:
    session = _session()
    _todo(session)

    result = TodayTodoMigrationService(session).migrate(user_id="user_1", dry_run=True)

    assert result.created == 1
    assert result.rows[0]["action"] == "would_create"
    assert len(session.query(TaskRow).all()) == 0


def test_today_read_path_surfaces_task_backed_todos() -> None:
    session = _session()
    _todo(session)
    TodayTodoMigrationService(session).migrate(user_id="user_1")

    page = EntryService(session).list_entries(start=date(2026, 5, 17), end=date(2026, 5, 17), kinds=["todo"])

    task_rows = [entry for entry in page.entries if entry["meta"].get("ref_kind") == "task"]
    assert len(task_rows) == 1
    assert task_rows[0]["id"].startswith("task:")


def test_failed_migration_rolls_back_row_without_task(monkeypatch) -> None:
    session = _session()
    row = _todo(session)

    def fail_create_task(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("alfred.services.tasks.task_service.TaskService.create_task", fail_create_task)

    try:
        TodayTodoMigrationService(session).migrate(user_id="user_1")
    except Exception:
        session.rollback()

    assert len(session.query(TaskRow).all()) == 0
    session.refresh(row)
    assert row.meta == {}
