"""Google Tasks API connector for Alfred.

Provides a thin wrapper around the Google Tasks API v1 that:
- Accepts Google OAuth credentials
- Refreshes credentials when needed via GoogleOAuthSession
- Exposes convenience helpers for listing task lists and tasks

Requires OAuth scope: https://www.googleapis.com/auth/tasks.readonly
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from alfred.connectors.google_oauth_session import (
    CredentialsRefreshedCallback,
    GoogleOAuthSession,
)

logger = logging.getLogger(__name__)


class GoogleTasksConnector:
    """Class for interacting with Google Tasks using Google OAuth credentials."""

    def __init__(
        self,
        credentials: Credentials,
        *,
        user_id: str | None = None,
        on_credentials_refreshed: CredentialsRefreshedCallback | None = None,
    ) -> None:
        """Initialize the connector.

        Args:
            credentials: Google OAuth Credentials object.
            user_id: Optional identifier for the user (for logging/metrics only).
            on_credentials_refreshed: Optional callback invoked after refresh with updated Credentials.
        """
        self._credentials = credentials
        self._user_id = user_id
        self._on_refresh = on_credentials_refreshed
        self._oauth_session = GoogleOAuthSession(
            credentials, on_credentials_refreshed=on_credentials_refreshed
        )
        self.service = None

    async def _get_credentials(self) -> Credentials:
        """Get valid Google OAuth credentials."""
        try:
            self._credentials = await self._oauth_session.get_credentials()
            return self._credentials
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to refresh Google OAuth credentials: {exc!s}") from exc

    async def _get_service(self):
        """Get the Google Tasks service instance using credentials."""
        if self.service:
            return self.service

        try:
            credentials = await self._get_credentials()
            self.service = build("tasks", "v1", credentials=credentials)
            return self.service
        except Exception as exc:
            raise RuntimeError(f"Failed to create Google Tasks service: {exc!s}") from exc

    @staticmethod
    async def _execute(request: Any) -> Any:
        """Execute a googleapiclient request in a worker thread."""
        return await asyncio.to_thread(request.execute)

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
