"""Base class for Google API connectors.

Extracts the shared OAuth credential management, service building, and
request execution that was duplicated across GoogleDriveConnector,
GoogleCalendarConnector, GoogleGmailConnector, and GoogleTasksConnector.

Subclasses set ``_SERVICE_NAME`` and ``_SERVICE_VERSION``, then use
``self._get_service()`` and ``self._execute(request)`` directly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from alfred.connectors.google_oauth_session import GoogleOAuthSession

CredentialsRefreshedCallback = Callable[[Credentials], Awaitable[None] | None] | None


class GoogleConnectorBase:
    """Shared Google API connector base.

    Subclasses must set:
        ``_SERVICE_NAME``    -- e.g. ``"drive"``, ``"calendar"``, ``"gmail"``
        ``_SERVICE_VERSION`` -- e.g. ``"v3"``, ``"v1"``
    """

    _SERVICE_NAME: ClassVar[str]
    _SERVICE_VERSION: ClassVar[str]

    def __init__(
        self,
        credentials: Credentials,
        user_id: str | None = None,
        on_credentials_refreshed: CredentialsRefreshedCallback = None,
    ) -> None:
        self._credentials = credentials
        self._user_id = user_id
        self._on_refresh = on_credentials_refreshed
        self._oauth_session = GoogleOAuthSession(
            credentials, on_credentials_refreshed=on_credentials_refreshed
        )
        self.service = None

    async def _get_credentials(self) -> Credentials:
        """Get valid Google OAuth credentials, refreshing if needed."""
        try:
            self._credentials = await self._oauth_session.get_credentials()
            return self._credentials
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to refresh Google OAuth credentials: {exc!s}") from exc

    async def _get_service(self) -> Any:
        """Get or create the Google API service instance."""
        if self.service:
            return self.service
        try:
            credentials = await self._get_credentials()
            self.service = build(
                self._SERVICE_NAME, self._SERVICE_VERSION, credentials=credentials
            )
            return self.service
        except Exception as exc:
            raise RuntimeError(
                f"Failed to create Google {self._SERVICE_NAME} service: {exc!s}"
            ) from exc

    @staticmethod
    async def _execute(request: Any) -> Any:
        """Execute a googleapiclient request in a worker thread."""
        return await asyncio.to_thread(request.execute)
