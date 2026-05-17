from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.services.tasks.exceptions import InvalidTimezoneError, TaskScheduleConflictError
from alfred.services.tasks.focus_service import TaskFocusService
from alfred.services.tasks.task_service import TaskService


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_schedule_focus_block_validates_timezone_and_conflicts() -> None:
    session = _session()
    task = TaskService(session).create_task(user_id="user_1", title="Focus")
    service = TaskFocusService(session)

    event = service.schedule_focus_block(
        user_id="user_1",
        title="Deep work",
        task_id=task.id,
        start_at=datetime(2026, 3, 8, 9, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 8, 10, 0, tzinfo=UTC),
        tz_name="America/Los_Angeles",
    )
    assert event.id is not None

    with pytest.raises(TaskScheduleConflictError):
        service.schedule_focus_block(
            user_id="user_1",
            title="Overlap",
            start_at=datetime(2026, 3, 8, 9, 30, tzinfo=UTC),
            end_at=datetime(2026, 3, 8, 10, 30, tzinfo=UTC),
        )

    with pytest.raises(InvalidTimezoneError):
        service.schedule_focus_block(
            user_id="user_1",
            title="Bad tz",
            start_at=datetime(2026, 3, 8, 11, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 8, 12, 0, tzinfo=UTC),
            tz_name="Not/AZone",
        )


def test_pomodoro_records_duration_and_reflection() -> None:
    session = _session()
    task = TaskService(session).create_task(user_id="user_1", title="Pomodoro")

    pomodoro = TaskFocusService(session).record_pomodoro(
        user_id="user_1",
        task_id=task.id or 0,
        start_time=datetime(2026, 5, 17, 10, 0, tzinfo=UTC),
        end_time=datetime(2026, 5, 17, 10, 25, tzinfo=UTC),
        duration_minutes=25,
        reflection_md="Stayed focused.",
    )

    assert pomodoro.duration_minutes == 25
    assert pomodoro.reflection_md == "Stayed focused."
