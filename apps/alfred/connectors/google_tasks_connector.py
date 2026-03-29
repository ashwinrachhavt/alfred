"""Google Tasks API connector for Alfred.

Provides a thin wrapper around the Google Tasks API v1 that:
- Accepts Google OAuth credentials
- Refreshes credentials when needed via GoogleConnectorBase
- Exposes convenience helpers for listing task lists and tasks

Requires OAuth scope: https://www.googleapis.com/auth/tasks.readonly
"""

from __future__ import annotations

import logging
from typing import Any

from alfred.connectors.google_base import GoogleConnectorBase

logger = logging.getLogger(__name__)


class GoogleTasksConnector(GoogleConnectorBase):
    """Class for interacting with Google Tasks using Google OAuth credentials."""

    _SERVICE_NAME = "tasks"
    _SERVICE_VERSION = "v1"

    async def list_task_lists(self) -> tuple[list[dict[str, Any]], str | None]:
        """List all task lists for the authenticated user.

        Returns:
            Tuple of (list of task list dicts, error string or None).
            Each task list includes: id, title, updated, selfLink.
        """
        try:
            service = await self._get_service()
            task_lists: list[dict[str, Any]] = []
            page_token: str | None = None

            while True:
                request_params: dict[str, Any] = {"maxResults": 100}
                if page_token:
                    request_params["pageToken"] = page_token

                request = service.tasklists().list(**request_params)
                result = await self._execute(request)
                task_lists.extend(result.get("items", []))

                page_token = result.get("nextPageToken")
                if not page_token:
                    break

            return task_lists, None

        except Exception as e:
            return [], f"Error listing task lists: {e!s}"

    async def list_tasks(
        self,
        tasklist_id: str,
        *,
        show_completed: bool = True,
        show_hidden: bool = False,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """List tasks in a task list.

        Each task includes: id, title, notes, status (needsAction/completed),
        due, completed, updated, parent, position.

        Args:
            tasklist_id: The ID of the task list.
            show_completed: Whether to include completed tasks.
            show_hidden: Whether to include hidden tasks.

        Returns:
            Tuple of (list of task dicts, error string or None).
        """
        try:
            service = await self._get_service()
            tasks: list[dict[str, Any]] = []
            page_token: str | None = None

            while True:
                request_params: dict[str, Any] = {
                    "tasklist": tasklist_id,
                    "maxResults": 100,
                    "showCompleted": show_completed,
                    "showHidden": show_hidden,
                }
                if page_token:
                    request_params["pageToken"] = page_token

                request = service.tasks().list(**request_params)
                result = await self._execute(request)
                tasks.extend(result.get("items", []))

                page_token = result.get("nextPageToken")
                if not page_token:
                    break

            return tasks, None

        except Exception as e:
            return [], f"Error listing tasks for {tasklist_id}: {e!s}"


__all__ = ["GoogleTasksConnector"]
