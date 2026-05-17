import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.services.tasks.exceptions import TaskAuthorizationError
from alfred.services.tasks.task_service import TaskService


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_task_crud_move_and_done_flow() -> None:
    session = _session()
    service = TaskService(session)

    task = service.create_task(user_id="user_1", title="Write tests", priority="HIGH")
    assert task.id is not None
    assert task.title == "Write tests"

    updated = service.update_task(task.id, user_id="user_1", patch={"title": "Write more tests", "tags": ["qa"]})
    assert updated.title == "Write more tests"
    assert updated.tags == ["qa"]

    done = service.mark_done(task.id, user_id="user_1")
    assert done.status == "DONE"
    assert done.completed_at is not None

    service.delete_task(task.id, user_id="user_1")
    assert service.list_tasks(user_id="user_1") == []


def test_task_user_scoping_rejects_other_users() -> None:
    session = _session()
    task = TaskService(session).create_task(user_id="user_1", title="Private")

    with pytest.raises(TaskAuthorizationError):
        TaskService(session).get_task(task.id or 0, user_id="user_2")
