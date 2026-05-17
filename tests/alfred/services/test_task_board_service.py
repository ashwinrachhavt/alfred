from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.models.tasks import TaskColumnRow
from alfred.services.tasks.board_service import STANDARD_COLUMNS, TaskBoardService


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_default_board_creates_standard_columns() -> None:
    session = _session()
    board = TaskBoardService(session).get_or_create_default_board("user_1")

    columns = TaskBoardService(session).list_columns(board.id or 0, "user_1")

    assert [column.name for column in columns] == [name for name, _position in STANDARD_COLUMNS]
    assert [column.position for column in columns] == [position for _name, position in STANDARD_COLUMNS]


def test_standard_column_repair_is_idempotent() -> None:
    session = _session()
    service = TaskBoardService(session)
    board = service.get_or_create_default_board("user_1")
    todo = service.get_todo_column(board.id or 0, "user_1")
    todo.name = "todo"
    todo.position = 99
    session.add(todo)
    session.commit()

    repaired = service.ensure_standard_columns(board.id or 0, user_id="user_1")
    repaired_again = service.ensure_standard_columns(board.id or 0, user_id="user_1")

    assert [(column.name, column.position) for column in repaired] == list(STANDARD_COLUMNS)
    assert [(column.name, column.position) for column in repaired_again] == list(STANDARD_COLUMNS)
    assert len(session.query(TaskColumnRow).all()) == len(STANDARD_COLUMNS)
