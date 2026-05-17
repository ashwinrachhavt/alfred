"""Migration bridge from legacy Today todos to task-system rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from alfred.models.tasks import TaskRow
from alfred.models.today import DailyEntryRow
from alfred.services.tasks.exceptions import TaskMigrationConflictError, TaskValidationError
from alfred.services.tasks.metrics import increment_task_metric
from alfred.services.tasks.task_service import TaskService

_STATUS_MAP = {
    "open": "TODO",
    "doing": "IN_PROGRESS",
    "done": "DONE",
    "skipped": "ARCHIVED",
}
_PRIORITY_MAP = {
    0: "LOW",
    1: "MEDIUM",
    2: "HIGH",
}


@dataclass(slots=True)
class TodayTodoMigrationResult:
    created: int = 0
    skipped: int = 0
    duplicates: int = 0
    invalid: int = 0
    rows: list[dict[str, Any]] | None = None


@dataclass(slots=True)
class TodayTodoMigrationService:
    session: Session

    def migrate(self, *, user_id: str | None = None, dry_run: bool = False) -> TodayTodoMigrationResult:
        rows = list(
            self.session.exec(
                select(DailyEntryRow)
                .where(DailyEntryRow.kind == "todo")
                .order_by(DailyEntryRow.entry_date.asc(), DailyEntryRow.id.asc())
            )
        )
        result = TodayTodoMigrationResult(rows=[])
        task_service = TaskService(self.session)
        for row in rows:
            increment_task_metric("migration_rows_processed")
            if row.id is None:
                result.invalid += 1
                result.rows.append({"entry_id": None, "action": "invalid", "reason": "missing id"})
                continue
            if user_id is not None and row.user_id not in {None, user_id}:
                result.skipped += 1
                result.rows.append({"entry_id": row.id, "action": "skipped", "reason": "different user"})
                continue
            title = (row.title or "").strip()
            if not title:
                result.invalid += 1
                result.rows.append({"entry_id": row.id, "action": "invalid", "reason": "empty title"})
                continue
            existing = self.session.exec(select(TaskRow).where(TaskRow.legacy_today_entry_id == row.id)).first()
            if existing is not None:
                result.duplicates += 1
                result.rows.append({"entry_id": row.id, "action": "duplicate", "task_id": existing.id})
                continue
            if dry_run:
                result.created += 1
                result.rows.append({"entry_id": row.id, "action": "would_create"})
                continue
            effective_user_id = (user_id or row.user_id or "dev-user").strip()
            if not effective_user_id:
                raise TaskValidationError("user_id is required for Today todo migration")
            try:
                task = task_service.create_task(
                    user_id=effective_user_id,
                    title=title,
                    description_md=row.body_md or "",
                    priority=_PRIORITY_MAP.get(int(row.priority), "MEDIUM"),
                    status=_STATUS_MAP.get(row.status, "TODO"),
                    tags=list(row.tags or []),
                    due_date=row.entry_date,
                    legacy_today_entry_id=row.id,
                    meta={"migrated_from_today": True, **dict(row.meta or {})},
                )
            except Exception as exc:
                raise TaskMigrationConflictError(f"failed to migrate Today entry {row.id}") from exc
            row.meta = {**dict(row.meta or {}), "task_id": task.id, "ref_kind": "task"}
            self.session.add(row)
            self.session.commit()
            result.created += 1
            result.rows.append({"entry_id": row.id, "action": "created", "task_id": task.id})
        return result


__all__ = ["TodayTodoMigrationResult", "TodayTodoMigrationService"]
