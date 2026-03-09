"""Todoist REST API connector for Alfred.

Fetches projects, tasks, and comments from a user's Todoist account.
Uses the REST API v2 for active tasks and Sync API v9 for completed tasks.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from alfred.core.settings import settings

logger = logging.getLogger(__name__)

TODOIST_REST_URL = "https://api.todoist.com/rest/v2"
TODOIST_SYNC_URL = "https://api.todoist.com/sync/v9"


class TodoistClient:
    """Sync client for the Todoist REST API v2."""

    def __init__(
        self,
        token: str | None = None,
        *,
        timeout_seconds: int = 30,
    ) -> None:
        configured = settings.todoist_token.get_secret_value() if settings.todoist_token else None
        self._token = token or configured
        if not self._token:
            raise RuntimeError("TODOIST_TOKEN is not configured")
        self._timeout = timeout_seconds
        self._headers = {
            "Authorization": f"Bearer {self._token}",
        }

    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        resp = httpx.get(url, headers=self._headers, params=params, timeout=self._timeout)
        resp.raise_for_status()
        return resp

    def list_projects(self) -> list[dict[str, Any]]:
        """List all projects for the authenticated user.

        Returns:
            List of project dicts with id, name, color, is_favorite, etc.
        """
        resp = self._get(f"{TODOIST_REST_URL}/projects")
        return resp.json()

    def list_tasks(
        self,
        *,
        project_id: str | None = None,
        filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """List active tasks, optionally filtered by project or Todoist filter string.

        Each task includes: id, content (title), description, project_id,
        section_id, labels, priority, due, created_at, is_completed, url.

        Args:
            project_id: Optional project ID to filter tasks.
            filter: Optional Todoist filter expression (e.g., "today", "overdue").
        """
        params: dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id
        if filter:
            params["filter"] = filter
        resp = self._get(f"{TODOIST_REST_URL}/tasks", params=params or None)
        return resp.json()

    def get_task_comments(self, task_id: str) -> list[dict[str, Any]]:
        """Get comments for a specific task.

        Each comment includes: id, content, posted_at.

        Args:
            task_id: The Todoist task ID.
        """
        resp = self._get(f"{TODOIST_REST_URL}/comments", params={"task_id": task_id})
        return resp.json()

    def list_completed_tasks(
        self,
        *,
        project_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """List completed tasks using the Todoist Sync API.

        Note: This uses a different endpoint (Sync API v9) than the REST API.

        Args:
            project_id: Optional project ID to filter completed tasks.
            limit: Maximum number of completed tasks to return (default 200).

        Returns:
            List of completed task items from the Sync API response.
        """
        params: dict[str, Any] = {"limit": min(limit, 200)}
        if project_id:
            params["project_id"] = project_id
        resp = self._get(f"{TODOIST_SYNC_URL}/completed/get_all", params=params)
        data = resp.json()
        return data.get("items", [])


__all__ = ["TodoistClient"]
