"""Task CRUD service for Alfred's task operating system."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlmodel import Session, col, select

from alfred.models.tasks import TaskPriority, TaskRow, TaskStatus, TaskType
from alfred.services.tasks.board_service import TaskBoardService
from alfred.services.tasks.exceptions import (
    TaskAuthorizationError,
    TaskBoardNotFoundError,
    TaskNotFoundError,
    TaskValidationError,
)

MAX_TITLE_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 50_000
MAX_TAGS = 50
MAX_TAG_LENGTH = 80


@dataclass(slots=True)
class TaskService:
    """User-scoped task CRUD and board movement operations."""

    session: Session

    def list_tasks(
        self,
        *,
        user_id: str,
        board_id: int | None = None,
        status: list[str] | None = None,
        priority: list[str] | None = None,
        project_id: int | None = None,
        source_kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TaskRow]:
        user_id = self._normalize_user_id(user_id)
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        stmt = select(TaskRow).where(TaskRow.user_id == user_id)
        if board_id is not None:
            stmt = stmt.where(TaskRow.board_id == board_id)
        if status:
            statuses = [self._validate_status(value) for value in status]
            stmt = stmt.where(col(TaskRow.status).in_(statuses))
        if priority:
            priorities = [self._validate_priority(value) for value in priority]
            stmt = stmt.where(col(TaskRow.priority).in_(priorities))
        if project_id is not None:
            stmt = stmt.where(TaskRow.project_id == project_id)
        if source_kind:
            stmt = stmt.where(TaskRow.source_kind == source_kind)
        stmt = stmt.order_by(TaskRow.updated_at.desc(), TaskRow.id.desc()).offset(offset).limit(limit)
        return list(self.session.exec(stmt))

    def get_task(self, task_id: int, *, user_id: str) -> TaskRow:
        user_id = self._normalize_user_id(user_id)
        task = self.session.get(TaskRow, task_id)
        if task is None:
            raise TaskNotFoundError("task not found")
        if task.user_id != user_id:
            raise TaskAuthorizationError("task not found")
        return task

    def create_task(
        self,
        *,
        user_id: str,
        title: str,
        description_md: str = "",
        board_id: int | None = None,
        column_id: int | None = None,
        priority: str = TaskPriority.MEDIUM,
        status: str = TaskStatus.TODO,
        type: str | None = None,
        estimate_minutes: int | None = None,
        estimated_pomodoros: int | None = None,
        tags: list[str] | None = None,
        due_at: datetime | None = None,
        due_date: date | None = None,
        source_kind: str | None = None,
        source_id: str | None = None,
        source_url: str | None = None,
        project_id: int | None = None,
        auto_generated: bool = False,
        ai_planned: bool = False,
        from_brain_dump: bool = False,
        legacy_today_entry_id: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> TaskRow:
        user_id = self._normalize_user_id(user_id)
        board_service = TaskBoardService(self.session)
        if board_id is None:
            board = board_service.get_or_create_default_board(user_id)
            board_id = board.id
            if board_id is None:
                raise TaskBoardNotFoundError("default board has no id")
        else:
            board_service.get_board_for_user(board_id, user_id)

        if column_id is None:
            column = board_service.get_todo_column(board_id, user_id)
            column_id = column.id
        else:
            column = board_service.get_column_for_user(column_id, user_id)
            if column.board_id != board_id:
                raise TaskValidationError("column does not belong to board")

        task = TaskRow(
            user_id=user_id,
            board_id=board_id,
            column_id=column_id,
            project_id=project_id,
            title=self._validate_title(title),
            description_md=self._validate_description(description_md),
            priority=self._validate_priority(priority),
            status=self._validate_status(status),
            type=self._validate_type(type) if type else None,
            estimate_minutes=self._validate_non_negative(estimate_minutes, "estimate_minutes"),
            estimated_pomodoros=self._validate_non_negative(estimated_pomodoros, "estimated_pomodoros"),
            tags=self._validate_tags(tags),
            due_at=due_at,
            due_date=due_date,
            source_kind=source_kind,
            source_id=source_id,
            source_url=source_url,
            auto_generated=auto_generated,
            ai_planned=ai_planned,
            from_brain_dump=from_brain_dump,
            legacy_today_entry_id=legacy_today_entry_id,
            meta=dict(meta or {}),
        )
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def create_many(self, *, user_id: str, tasks: list[dict[str, Any]]) -> list[TaskRow]:
        created: list[TaskRow] = []
        for payload in tasks:
            created.append(self.create_task(user_id=user_id, **payload))
        return created

    def update_task(self, task_id: int, *, user_id: str, patch: dict[str, Any]) -> TaskRow:
        task = self.get_task(task_id, user_id=user_id)
        board_service = TaskBoardService(self.session)
        allowed = {
            "title",
            "description_md",
            "priority",
            "status",
            "type",
            "estimate_minutes",
            "estimated_pomodoros",
            "tags",
            "due_at",
            "due_date",
            "source_kind",
            "source_id",
            "source_url",
            "project_id",
            "meta",
        }
        for key, value in patch.items():
            if key not in allowed:
                continue
            if key == "title":
                task.title = self._validate_title(str(value))
            elif key == "description_md":
                task.description_md = self._validate_description(str(value or ""))
            elif key == "priority":
                task.priority = self._validate_priority(str(value))
            elif key == "status":
                task.status = self._validate_status(str(value))
                if task.status == TaskStatus.DONE and task.completed_at is None:
                    task.completed_at = datetime.now(UTC)
            elif key == "type":
                task.type = self._validate_type(str(value)) if value else None
            elif key in {"estimate_minutes", "estimated_pomodoros"}:
                setattr(task, key, self._validate_non_negative(value, key))
            elif key == "tags":
                task.tags = self._validate_tags(value)
            elif key == "meta":
                task.meta = dict(value or {})
            else:
                setattr(task, key, value)

        if task.column_id is not None:
            board_service.get_column_for_user(task.column_id, user_id)
        task.updated_at = datetime.now(UTC)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def delete_task(self, task_id: int, *, user_id: str) -> None:
        task = self.get_task(task_id, user_id=user_id)
        self.session.delete(task)
        self.session.commit()

    def move_task(self, task_id: int, *, column_id: int, user_id: str) -> TaskRow:
        task = self.get_task(task_id, user_id=user_id)
        column = TaskBoardService(self.session).get_column_for_user(column_id, user_id)
        if column.board_id != task.board_id:
            raise TaskValidationError("column does not belong to task board")
        task.column_id = column_id
        task.updated_at = datetime.now(UTC)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def mark_done(self, task_id: int, *, user_id: str) -> TaskRow:
        task = self.get_task(task_id, user_id=user_id)
        done_column = TaskBoardService(self.session).get_done_column(task.board_id, user_id)
        if done_column.id is None:
            raise TaskBoardNotFoundError("done column has no id")
        task.column_id = done_column.id
        task.status = TaskStatus.DONE
        task.completed_at = task.completed_at or datetime.now(UTC)
        task.updated_at = datetime.now(UTC)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    @staticmethod
    def _normalize_user_id(user_id: str) -> str:
        normalized = (user_id or "").strip()
        if not normalized:
            raise TaskValidationError("user_id is required")
        return normalized

    @staticmethod
    def _validate_title(title: str) -> str:
        normalized = (title or "").strip()
        if not normalized:
            raise TaskValidationError("Title is required")
        if len(normalized) > MAX_TITLE_LENGTH:
            raise TaskValidationError(f"Title must be {MAX_TITLE_LENGTH} characters or fewer")
        return normalized

    @staticmethod
    def _validate_description(value: str) -> str:
        if len(value or "") > MAX_DESCRIPTION_LENGTH:
            raise TaskValidationError("Description is too long")
        return value or ""

    @staticmethod
    def _validate_priority(value: str) -> str:
        try:
            return TaskPriority(value).value
        except ValueError as exc:
            raise TaskValidationError("Invalid priority") from exc

    @staticmethod
    def _validate_status(value: str) -> str:
        try:
            return TaskStatus(value).value
        except ValueError as exc:
            raise TaskValidationError("Invalid task status") from exc

    @staticmethod
    def _validate_type(value: str) -> str:
        try:
            return TaskType(value).value
        except ValueError as exc:
            raise TaskValidationError("Invalid task type") from exc

    @staticmethod
    def _validate_non_negative(value: int | None, field_name: str) -> int | None:
        if value is None:
            return None
        numeric = int(value)
        if numeric < 0:
            raise TaskValidationError(f"{field_name} must be non-negative")
        return numeric

    @staticmethod
    def _validate_tags(tags: list[str] | None) -> list[str]:
        normalized = []
        for tag in tags or []:
            value = str(tag).strip()
            if not value:
                continue
            if len(value) > MAX_TAG_LENGTH:
                raise TaskValidationError(f"Tags must be {MAX_TAG_LENGTH} characters or fewer")
            if value not in normalized:
                normalized.append(value)
        if len(normalized) > MAX_TAGS:
            raise TaskValidationError(f"At most {MAX_TAGS} tags are allowed")
        return normalized


__all__ = ["TaskService"]
