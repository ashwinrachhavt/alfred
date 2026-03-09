"""Google Drive Connector.

Provides a thin wrapper around the Google Drive API v3 that:
- Accepts Google OAuth credentials
- Refreshes credentials when needed via GoogleOAuthSession
- Exposes convenience helpers for listing, exporting, and downloading Drive files
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from alfred.connectors.google_oauth_session import GoogleOAuthSession

GOOGLE_DOCS_MIME_TYPE = "application/vnd.google-apps.document"


class GoogleDriveConnector:
    """Class for interacting with Google Drive using Google OAuth credentials."""

    def __init__(
        self,
        credentials: Credentials,
        user_id: str | None = None,
        on_credentials_refreshed: Callable[[Credentials], Awaitable[None] | None] | None = None,
    ):
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
        """Get the Google Drive service instance using credentials."""
        if self.service:
            return self.service

        try:
            credentials = await self._get_credentials()
            self.service = build("drive", "v3", credentials=credentials)
            return self.service
        except Exception as exc:
            raise RuntimeError(f"Failed to create Google Drive service: {exc!s}") from exc

    @staticmethod
    async def _execute(request: Any) -> Any:
        """Execute a googleapiclient request in a worker thread."""
        return await asyncio.to_thread(request.execute)

    async def list_files(
        self,
        query: str | None = None,
        mime_type: str | None = None,
        page_size: int = 100,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """List files in the user's Google Drive.

        Args:
            query: Optional Drive search query (uses Drive API q syntax).
            mime_type: Optional MIME type filter (e.g., ``application/vnd.google-apps.document``).
            page_size: Maximum results per page (up to 1000).

        Returns:
            Tuple of (list of file metadata dicts, error string or None).
        """
        try:
            service = await self._get_service()

            q_parts: list[str] = ["trashed = false"]
            if mime_type:
                q_parts.append(f"mimeType = '{mime_type}'")
            if query:
                q_parts.append(query)
            q = " and ".join(q_parts)

            files: list[dict[str, Any]] = []
            page_token: str | None = None

            while True:
                request_params: dict[str, Any] = {
                    "q": q,
                    "pageSize": min(page_size, 1000),
                    "fields": (
                        "nextPageToken, files(id, name, mimeType, modifiedTime, "
                        "createdTime, owners, webViewLink, size)"
                    ),
                }
                if page_token:
                    request_params["pageToken"] = page_token

                request = service.files().list(**request_params)
                result = await self._execute(request)
                files.extend(result.get("files", []))

                page_token = result.get("nextPageToken")
                if not page_token:
                    break

            return files, None

        except Exception as e:
            return [], f"Error listing Drive files: {e!s}"

    async def list_docs(self) -> tuple[list[dict[str, Any]], str | None]:
        """Convenience method to list Google Docs files.

        Returns:
            Tuple of (list of Google Docs file metadata dicts, error string or None).
        """
        return await self.list_files(mime_type=GOOGLE_DOCS_MIME_TYPE)

    async def export_doc(
        self,
        file_id: str,
        mime_type: str = "text/plain",
    ) -> tuple[str, str | None]:
        """Export a Google Doc as the specified MIME type.

        Google-native files (Docs, Sheets, Slides) must be exported rather than
        downloaded directly.

        Args:
            file_id: The Drive file ID of the Google Doc.
            mime_type: The target export MIME type (default: ``text/plain``).

        Returns:
            Tuple of (exported content as string, error string or None).
        """
        try:
            service = await self._get_service()
            request = service.files().export(fileId=file_id, mimeType=mime_type)
            content = await self._execute(request)

            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")

            return content, None

        except Exception as e:
            return "", f"Error exporting doc {file_id}: {e!s}"

    async def get_file_metadata(
        self,
        file_id: str,
    ) -> tuple[dict[str, Any], str | None]:
        """Get detailed metadata for a specific file.

        Args:
            file_id: The Drive file ID.

        Returns:
            Tuple of (file metadata dict, error string or None).
        """
        try:
            service = await self._get_service()
            request = service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, modifiedTime, createdTime, owners, webViewLink, size",
            )
            metadata = await self._execute(request)
            return metadata, None

        except Exception as e:
            return {}, f"Error fetching metadata for {file_id}: {e!s}"

    async def download_file(
        self,
        file_id: str,
    ) -> tuple[bytes, str | None]:
        """Download a non-Google-native file as bytes.

        For Google-native files (Docs, Sheets, Slides) use :meth:`export_doc` instead.

        Args:
            file_id: The Drive file ID.

        Returns:
            Tuple of (file content as bytes, error string or None).
        """
        try:
            service = await self._get_service()
            request = service.files().get_media(fileId=file_id)
            content = await self._execute(request)

            if isinstance(content, str):
                content = content.encode("utf-8")

            return content, None

        except Exception as e:
            return b"", f"Error downloading file {file_id}: {e!s}"
