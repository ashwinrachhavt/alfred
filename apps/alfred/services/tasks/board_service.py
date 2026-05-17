"""Board and column service for Alfred tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from alfred.models.tasks import TaskBoardRow, TaskColumnRow
from alfred.services.tasks.exceptions import TaskBoardNotFoundError, TaskColumnInvariantError

STANDARD_COLUMNS: tuple[tuple[str, int], ...] = (
    ("Backlog", 0),
    ("Todo", 1),
    ("In Progress", 2),
    ("Done", 3),
)


@dataclass(slots=True)
class TaskBoardService:
    """Manage user-scoped task boards and standard kanban columns."""

    session: Session

    def get_or_create_default_board(self, user_id: str) -> TaskBoardRow:
        """Return the user's default board, creating and repairing it as needed."""

        user_id = self._normalize_user_id(user_id)
        board = self.session.exec(
            select(TaskBoardRow)
            .where(TaskBoardRow.user_id == user_id)
            .where(TaskBoardRow.is_default == True)  # noqa: E712 - SQLModel expression
            .order_by(TaskBoardRow.id)
        ).first()
        if board is None:
            board = TaskBoardRow(
                user_id=user_id,
                title="Personal Kanban",
                description="Auto-created default task board",
                is_default=True,
            )
            self.session.add(board)
            try:
                self.session.commit()
            except IntegrityError:
                self.session.rollback()
                board = self.session.exec(
                    select(TaskBoardRow)
                    .where(TaskBoardRow.user_id == user_id)
                    .where(TaskBoardRow.is_default == True)  # noqa: E712
                    .order_by(TaskBoardRow.id)
                ).first()
                if board is None:
                    raise TaskColumnInvariantError("default board could not be created") from None
            else:
                self.session.refresh(board)

        self.ensure_standard_columns(board.id, user_id=user_id)
        self.session.refresh(board)
        return board

    def get_board_for_user(self, board_id: int, user_id: str) -> TaskBoardRow:
        user_id = self._normalize_user_id(user_id)
        board = self.session.get(TaskBoardRow, board_id)
        if board is None or board.user_id != user_id:
            raise TaskBoardNotFoundError("board not found")
        return board

    def list_boards(self, user_id: str) -> list[TaskBoardRow]:
        user_id = self._normalize_user_id(user_id)
        return list(
            self.session.exec(
                select(TaskBoardRow)
                .where(TaskBoardRow.user_id == user_id)
                .order_by(TaskBoardRow.is_default.desc(), TaskBoardRow.created_at.asc(), TaskBoardRow.id.asc())
            )
        )

    def list_columns(self, board_id: int, user_id: str) -> list[TaskColumnRow]:
        self.get_board_for_user(board_id, user_id)
        return list(
            self.session.exec(
                select(TaskColumnRow)
                .where(TaskColumnRow.board_id == board_id)
                .order_by(TaskColumnRow.position.asc(), TaskColumnRow.id.asc())
            )
        )

    def get_column_for_user(self, column_id: int, user_id: str) -> TaskColumnRow:
        column = self.session.get(TaskColumnRow, column_id)
        if column is None:
            raise TaskBoardNotFoundError("column not found")
        self.get_board_for_user(column.board_id, user_id)
        return column

    def get_todo_column(self, board_id: int, user_id: str) -> TaskColumnRow:
        return self._get_named_column(board_id, user_id, "todo")

    def get_done_column(self, board_id: int, user_id: str) -> TaskColumnRow:
        return self._get_named_column(board_id, user_id, "done")

    def ensure_standard_columns(self, board_id: int, *, user_id: str) -> list[TaskColumnRow]:
        """Idempotently create or repair Backlog/Todo/In Progress/Done columns."""

        board = self.get_board_for_user(board_id, user_id)
        existing = {
            column.name.strip().casefold(): column
            for column in self.session.exec(select(TaskColumnRow).where(TaskColumnRow.board_id == board.id))
        }
        changed = False
        now = datetime.now(UTC)

        for name, position in STANDARD_COLUMNS:
            key = name.casefold()
            column = existing.get(key)
            if column is None:
                self.session.add(TaskColumnRow(board_id=board.id, name=name, position=position))
                changed = True
                continue
            if column.position != position or column.name != name:
                column.name = name
                column.position = position
                column.updated_at = now
                self.session.add(column)
                changed = True

        if changed:
            try:
                self.session.commit()
            except IntegrityError as exc:
                self.session.rollback()
                raise TaskColumnInvariantError("standard columns could not be repaired") from exc

        columns = self.list_columns(board.id, user_id)
        missing = {name.casefold() for name, _ in STANDARD_COLUMNS} - {
            column.name.strip().casefold() for column in columns
        }
        if missing:
            raise TaskColumnInvariantError(f"missing standard columns: {sorted(missing)}")
        return columns

    def _get_named_column(self, board_id: int, user_id: str, needle: str) -> TaskColumnRow:
        columns = self.ensure_standard_columns(board_id, user_id=user_id)
        for column in columns:
            if needle in column.name.casefold():
                return column
        raise TaskColumnInvariantError(f"{needle} column not found")

    @staticmethod
    def _normalize_user_id(user_id: str) -> str:
        normalized = (user_id or "").strip()
        if not normalized:
            raise TaskBoardNotFoundError("user_id is required")
        return normalized


__all__ = ["STANDARD_COLUMNS", "TaskBoardService"]
