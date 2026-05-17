"""Task learning capture service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from alfred.models.tasks import TaskLearningRow
from alfred.services.tasks.exceptions import TaskValidationError
from alfred.services.tasks.task_service import TaskService


@dataclass(slots=True)
class TaskLearningService:
    session: Session

    def add_learning(
        self,
        *,
        user_id: str,
        task_id: int,
        summary: str,
        details: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        confidence: float | None = None,
    ) -> TaskLearningRow:
        user_id = self._normalize_user_id(user_id)
        TaskService(self.session).get_task(task_id, user_id=user_id)
        normalized_summary = (summary or "").strip()
        if not normalized_summary:
            raise TaskValidationError("learning summary is required")
        if confidence is not None and not 0 <= confidence <= 1:
            raise TaskValidationError("learning confidence must be between 0 and 1")
        learning = TaskLearningRow(
            user_id=user_id,
            task_id=task_id,
            summary=normalized_summary,
            details=details,
            tags=[str(tag).strip() for tag in tags or [] if str(tag).strip()],
            confidence=confidence,
        )
        self.session.add(learning)
        self.session.commit()
        self.session.refresh(learning)
        return learning

    def record_completion_reflection(
        self,
        *,
        user_id: str,
        task_id: int,
        reflection_md: str | None,
    ) -> TaskLearningRow | None:
        reflection = (reflection_md or "").strip()
        if not reflection:
            return None
        return self.add_learning(
            user_id=user_id,
            task_id=task_id,
            summary=reflection[:500],
            details={"source": "task_completion_reflection", "reflection_md": reflection},
            tags=["task-completion"],
            confidence=0.8,
        )

    def record_pomodoro_reflection(
        self,
        *,
        user_id: str,
        task_id: int,
        reflection_md: str | None,
        duration_minutes: int | None = None,
    ) -> TaskLearningRow | None:
        reflection = (reflection_md or "").strip()
        if not reflection:
            return None
        return self.add_learning(
            user_id=user_id,
            task_id=task_id,
            summary=reflection[:500],
            details={
                "source": "pomodoro_reflection",
                "reflection_md": reflection,
                "duration_minutes": duration_minutes,
            },
            tags=["pomodoro", "focus"],
            confidence=0.75,
        )

    def list_recent_learnings(self, *, user_id: str, limit: int = 20) -> list[TaskLearningRow]:
        user_id = self._normalize_user_id(user_id)
        return list(
            self.session.exec(
                select(TaskLearningRow)
                .where(TaskLearningRow.user_id == user_id)
                .order_by(TaskLearningRow.created_at.desc(), TaskLearningRow.id.desc())
                .limit(max(1, min(limit, 100)))
            )
        )

    @staticmethod
    def _normalize_user_id(user_id: str) -> str:
        normalized = (user_id or "").strip()
        if not normalized:
            raise TaskValidationError("user_id is required")
        return normalized


__all__ = ["TaskLearningService"]
