"""Project grouping service for Alfred tasks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session, select

from alfred.models.tasks import ProjectStatus, TaskProjectRow
from alfred.services.tasks.exceptions import (
    TaskAuthorizationError,
    TaskNotFoundError,
    TaskValidationError,
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
class TaskProjectService:
    session: Session

    def list_projects(self, *, user_id: str, status: str | None = None) -> list[TaskProjectRow]:
        user_id = self._normalize_user_id(user_id)
        stmt = select(TaskProjectRow).where(TaskProjectRow.user_id == user_id)
        if status:
            stmt = stmt.where(TaskProjectRow.status == self._validate_status(status))
        return list(self.session.exec(stmt.order_by(TaskProjectRow.updated_at.desc(), TaskProjectRow.id.desc())))

    def get_project(self, project_id: int, *, user_id: str) -> TaskProjectRow:
        user_id = self._normalize_user_id(user_id)
        project = self.session.get(TaskProjectRow, project_id)
        if project is None:
            raise TaskNotFoundError("project not found")
        if project.user_id != user_id:
            raise TaskAuthorizationError("project not found")
        return project

    def create_project(
        self,
        *,
        user_id: str,
        title: str,
        description: str | None = None,
        slug: str | None = None,
        status: str = ProjectStatus.ACTIVE,
        notion_url: str | None = None,
    ) -> TaskProjectRow:
        user_id = self._normalize_user_id(user_id)
        normalized_title = self._validate_title(title)
        normalized_slug = self._unique_slug(user_id, slug or normalized_title)
        project = TaskProjectRow(
            user_id=user_id,
            slug=normalized_slug,
            title=normalized_title,
            description=description,
            status=self._validate_status(status),
            notion_url=notion_url,
        )
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)
        return project

    def update_project(self, project_id: int, *, user_id: str, patch: dict) -> TaskProjectRow:
        project = self.get_project(project_id, user_id=user_id)
        if "title" in patch:
            project.title = self._validate_title(str(patch["title"]))
        if "description" in patch:
            project.description = patch["description"]
        if "status" in patch:
            project.status = self._validate_status(str(patch["status"]))
        if "notion_url" in patch:
            project.notion_url = patch["notion_url"]
        project.updated_at = datetime.now(UTC)
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)
        return project

    def _unique_slug(self, user_id: str, value: str) -> str:
        base = _SLUG_RE.sub("-", value.lower()).strip("-") or "project"
        slug = base[:240]
        counter = 2
        while self.session.exec(
            select(TaskProjectRow).where(TaskProjectRow.user_id == user_id).where(TaskProjectRow.slug == slug)
        ).first():
            suffix = f"-{counter}"
            slug = f"{base[: 255 - len(suffix)]}{suffix}"
            counter += 1
        return slug

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
            raise TaskValidationError("Project title is required")
        if len(normalized) > 500:
            raise TaskValidationError("Project title must be 500 characters or fewer")
        return normalized

    @staticmethod
    def _validate_status(status: str) -> str:
        try:
            return ProjectStatus(status).value
        except ValueError as exc:
            raise TaskValidationError("Invalid project status") from exc


__all__ = ["TaskProjectService"]
