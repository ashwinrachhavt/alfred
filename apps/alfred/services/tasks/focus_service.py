"""Calendar, focus session, and pomodoro service for Alfred tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlmodel import Session, col, select

from alfred.models.tasks import (
    TaskCalendarEventRow,
    TaskEventType,
    TaskFocusSessionRow,
    TaskPomodoroSessionRow,
)
from alfred.services.tasks.exceptions import (
    InvalidTimezoneError,
    TaskScheduleConflictError,
    TaskValidationError,
)
from alfred.services.tasks.task_service import TaskService


@dataclass(slots=True)
class TaskFocusService:
    session: Session

    def schedule_focus_block(
        self,
        *,
        user_id: str,
        title: str,
        start_at: datetime,
        end_at: datetime,
        task_id: int | None = None,
        tz_name: str = "UTC",
        description_md: str | None = None,
        location: str | None = None,
        tags: list[str] | None = None,
    ) -> TaskCalendarEventRow:
        user_id = self._normalize_user_id(user_id)
        self._resolve_timezone(tz_name)
        start_at = self._ensure_aware(start_at)
        end_at = self._ensure_aware(end_at)
        if end_at <= start_at:
            raise TaskValidationError("end_at must be after start_at")
        if task_id is not None:
            TaskService(self.session).get_task(task_id, user_id=user_id)
        self._raise_on_conflict(user_id=user_id, start_at=start_at, end_at=end_at)
        event = TaskCalendarEventRow(
            user_id=user_id,
            task_id=task_id,
            title=self._validate_title(title),
            type=TaskEventType.FOCUS,
            start_at=start_at,
            end_at=end_at,
            description_md=description_md,
            location=location,
            tags=list(tags or []),
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def start_focus_session(
        self,
        *,
        user_id: str,
        task_id: int | None = None,
        event_id: int | None = None,
        started_at: datetime | None = None,
    ) -> TaskFocusSessionRow:
        user_id = self._normalize_user_id(user_id)
        if task_id is not None:
            TaskService(self.session).get_task(task_id, user_id=user_id)
        if event_id is not None:
            event = self.session.get(TaskCalendarEventRow, event_id)
            if event is None or event.user_id != user_id:
                raise TaskValidationError("event not found")
        session = TaskFocusSessionRow(
            user_id=user_id,
            task_id=task_id,
            event_id=event_id,
            started_at=self._ensure_aware(started_at or datetime.now(UTC)),
        )
        self.session.add(session)
        self.session.commit()
        self.session.refresh(session)
        return session

    def complete_focus_session(
        self,
        session_id: int,
        *,
        user_id: str,
        ended_at: datetime | None = None,
        interruptions: int | None = None,
    ) -> TaskFocusSessionRow:
        user_id = self._normalize_user_id(user_id)
        focus = self.session.get(TaskFocusSessionRow, session_id)
        if focus is None or focus.user_id != user_id:
            raise TaskValidationError("focus session not found")
        focus.ended_at = self._ensure_aware(ended_at or datetime.now(UTC))
        focus.completed = True
        if interruptions is not None:
            focus.interruptions = max(0, int(interruptions))
        self.session.add(focus)
        self.session.commit()
        self.session.refresh(focus)
        return focus

    def record_pomodoro(
        self,
        *,
        user_id: str,
        task_id: int,
        start_time: datetime,
        end_time: datetime,
        duration_minutes: int,
        reflection_md: str | None = None,
        status: str = "completed",
    ) -> TaskPomodoroSessionRow:
        user_id = self._normalize_user_id(user_id)
        TaskService(self.session).get_task(task_id, user_id=user_id)
        start_time = self._ensure_aware(start_time)
        end_time = self._ensure_aware(end_time)
        if end_time <= start_time:
            raise TaskValidationError("end_time must be after start_time")
        if duration_minutes <= 0:
            raise TaskValidationError("duration_minutes must be positive")
        pomodoro = TaskPomodoroSessionRow(
            user_id=user_id,
            task_id=task_id,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            reflection_md=reflection_md,
            status=status,
        )
        self.session.add(pomodoro)
        task = TaskService(self.session).get_task(task_id, user_id=user_id)
        task.completed_pomodoros += 1
        task.updated_at = datetime.now(UTC)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(pomodoro)
        return pomodoro

    def list_events(self, *, user_id: str, start_at: datetime, end_at: datetime) -> list[TaskCalendarEventRow]:
        user_id = self._normalize_user_id(user_id)
        start_at = self._ensure_aware(start_at)
        end_at = self._ensure_aware(end_at)
        return list(
            self.session.exec(
                select(TaskCalendarEventRow)
                .where(TaskCalendarEventRow.user_id == user_id)
                .where(TaskCalendarEventRow.start_at < end_at)
                .where(TaskCalendarEventRow.end_at > start_at)
                .order_by(TaskCalendarEventRow.start_at.asc(), TaskCalendarEventRow.id.asc())
            )
        )

    def _raise_on_conflict(self, *, user_id: str, start_at: datetime, end_at: datetime) -> None:
        conflict = self.session.exec(
            select(TaskCalendarEventRow)
            .where(TaskCalendarEventRow.user_id == user_id)
            .where(TaskCalendarEventRow.start_at < end_at)
            .where(TaskCalendarEventRow.end_at > start_at)
            .where(col(TaskCalendarEventRow.type) == TaskEventType.FOCUS)
        ).first()
        if conflict is not None:
            raise TaskScheduleConflictError("focus block overlaps another focus block")

    @staticmethod
    def _resolve_timezone(tz_name: str) -> ZoneInfo:
        try:
            return ZoneInfo(tz_name)
        except ZoneInfoNotFoundError as exc:
            raise InvalidTimezoneError(f"invalid timezone: {tz_name}") from exc

    @staticmethod
    def _ensure_aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

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
            raise TaskValidationError("title is required")
        if len(normalized) > 500:
            raise TaskValidationError("title must be 500 characters or fewer")
        return normalized


__all__ = ["TaskFocusService"]
