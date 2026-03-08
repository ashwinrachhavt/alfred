"""Ingest Google Drive documents into Alfred's document store.

This module:
- Lists all Google Docs the user has access to
- Exports each doc as plain text
- Upserts into Alfred ``documents`` using a stable hash: ``gdrive:{file_id}``
- Supports incremental sync via ``since`` (Drive ``modifiedTime`` filter)

Auth: Uses Google OAuth credentials resolved via ``alfred.services.google_oauth``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from google.oauth2.credentials import Credentials

from alfred.connectors.google_drive_connector import GOOGLE_DOCS_MIME_TYPE, GoogleDriveConnector
from alfred.core.exceptions import ConfigurationError
from alfred.schemas.documents import DocumentIngest
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.google_oauth import load_credentials, persist_credentials

logger = logging.getLogger(__name__)


def _parse_iso(dt: str | datetime | None) -> datetime | None:
    """Parse an ISO datetime string into an aware datetime (UTC)."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    dt = dt.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(dt)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except Exception:
        return None


def resolve_google_drive_credentials(
    *,
    user_id: str | None = None,
    namespace: str | None = None,
) -> tuple[Credentials, dict[str, Any]]:
    """Resolve Google OAuth credentials for Drive access.

    Args:
        user_id: Optional user identifier for multi-user token storage.
        namespace: Optional namespace for token storage partitioning.

    Returns:
        Tuple of (Credentials, info dict describing the token source).

    Raises:
        ConfigurationError: If no valid credentials can be found.
    """
    kwargs: dict[str, Any] = {}
    if user_id:
        kwargs["user_id"] = user_id
    if namespace:
        kwargs["namespace"] = namespace

    creds = load_credentials(**kwargs)
    if creds is None:
        raise ConfigurationError(
            "No Google OAuth credentials found. "
            "Complete Google OAuth flow first (connect via /api/google/auth)."
        )

    return creds, {"source": "oauth", "user_id": user_id or "default"}


class GoogleDriveImporter:
    """Fetch Google Docs and upsert them into Alfred's document store."""

    def __init__(
        self,
        *,
        credentials: Credentials,
        user_id: str | None = None,
        namespace: str | None = None,
    ) -> None:
        self._user_id = user_id
        self._namespace = namespace

        async def _on_refresh(updated_creds: Credentials) -> None:
            persist_credentials(user_id, updated_creds, namespace=namespace or None)

        self.connector = GoogleDriveConnector(
            credentials,
            user_id=user_id,
            on_credentials_refreshed=_on_refresh,
        )

    async def import_docs(
        self,
        *,
        doc_store: DocStorageService,
        limit: int | None = None,
        since: str | datetime | None = None,
    ) -> dict[str, Any]:
        """Import Google Docs into Alfred's document store.

        Args:
            doc_store: Alfred document storage service.
            limit: Maximum number of docs to import (None = unlimited).
            since: Only import docs modified after this datetime (ISO string or datetime).

        Returns:
            Summary dict with counts and document mapping.
        """
        since_dt = _parse_iso(since) if since else None

        # Build the Drive query
        query_parts: list[str] = []
        if since_dt:
            # Drive API expects RFC 3339 format for modifiedTime queries
            since_str = since_dt.strftime("%Y-%m-%dT%H:%M:%S")
            query_parts.append(f"modifiedTime > '{since_str}'")

        query = " and ".join(query_parts) if query_parts else None

        # List all Google Docs
        files, error = await self.connector.list_files(
            query=query,
            mime_type=GOOGLE_DOCS_MIME_TYPE,
        )
        if error:
            return {
                "ok": False,
                "error": error,
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "errors": [],
                "documents": [],
            }

        created = 0
        updated = 0
        skipped = 0
        errors: list[dict[str, str]] = []
        documents: list[dict[str, str]] = []

        for file_meta in files:
            if limit is not None and (created + updated) >= limit:
                break

            file_id = file_meta.get("id")
            if not file_id:
                skipped += 1
                continue

            try:
                # Export the Google Doc as plain text
                text, export_error = await self.connector.export_doc(file_id, mime_type="text/plain")
                if export_error:
                    errors.append({"file_id": file_id, "error": export_error})
                    continue

                cleaned_text = (text or "").strip()
                if not cleaned_text:
                    skipped += 1
                    continue

                name = file_meta.get("name", "Untitled")
                source_url = f"https://docs.google.com/document/d/{file_id}"
                stable_hash = f"gdrive:{file_id}"

                drive_meta = {
                    "file_id": file_id,
                    "name": name,
                    "mimeType": file_meta.get("mimeType"),
                    "modifiedTime": file_meta.get("modifiedTime"),
                    "createdTime": file_meta.get("createdTime"),
                    "owners": file_meta.get("owners"),
                    "webViewLink": file_meta.get("webViewLink"),
                }

                ingest = DocumentIngest(
                    source_url=source_url,
                    title=name,
                    content_type="google_doc",
                    cleaned_text=cleaned_text,
                    hash=stable_hash,
                    metadata={"source": "google_drive", "google_drive": drive_meta},
                )

                res = doc_store.ingest_document_store_only(ingest)
                doc_id = str(res["id"])
                if res.get("duplicate"):
                    updated += 1
                    doc_store.update_document_text(
                        doc_id,
                        title=name,
                        cleaned_text=cleaned_text,
                        metadata_update={"source": "google_drive", "google_drive": drive_meta},
                    )
                else:
                    created += 1

                documents.append({"file_id": file_id, "document_id": doc_id})

            except Exception as exc:
                logger.exception("Google Drive import failed for %s", file_id)
                errors.append({"file_id": str(file_id), "error": str(exc)})

        return {
            "ok": True,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "documents": documents,
        }


def import_google_drive_docs(
    *,
    doc_store: DocStorageService,
    user_id: str | None = None,
    namespace: str | None = None,
    limit: int | None = None,
    since: str | datetime | None = None,
) -> dict[str, Any]:
    """Convenience wrapper to import Google Docs into the document store.

    This is the main entry point for callers. It resolves credentials, creates the
    importer, and runs the async import in a synchronous context.

    Args:
        doc_store: Alfred document storage service.
        user_id: Optional user identifier for token lookup.
        namespace: Optional namespace for token storage partitioning.
        limit: Maximum number of docs to import.
        since: Only import docs modified after this datetime.

    Returns:
        Summary dict with counts, document mapping, and token info.
    """
    creds, token_info = resolve_google_drive_credentials(
        user_id=user_id, namespace=namespace
    )
    importer = GoogleDriveImporter(
        credentials=creds, user_id=user_id, namespace=namespace
    )

    # Run the async import - use existing event loop if available, otherwise create one
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're already in an async context; caller should await import_docs directly.
        # Fall back to creating a new loop in a thread.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(
                asyncio.run,
                importer.import_docs(doc_store=doc_store, limit=limit, since=since),
            ).result()
    else:
        result = asyncio.run(
            importer.import_docs(doc_store=doc_store, limit=limit, since=since)
        )

    result["token"] = token_info
    return result


__all__ = [
    "GoogleDriveImporter",
    "import_google_drive_docs",
    "resolve_google_drive_credentials",
]
