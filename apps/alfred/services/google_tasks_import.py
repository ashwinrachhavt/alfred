"""Ingest Google Tasks into Alfred's document store.

Each task list becomes a single document containing all its tasks rendered as
Markdown. Uses Google OAuth credentials resolved via ``alfred.services.google_oauth``.

Requires OAuth scope: https://www.googleapis.com/auth/tasks.readonly
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from google.oauth2.credentials import Credentials

from alfred.connectors.google_tasks_connector import GoogleTasksConnector
from alfred.core.exceptions import ConfigurationError
from alfred.schemas.documents import DocumentIngest
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.google_oauth import load_credentials, persist_credentials

logger = logging.getLogger(__name__)


def _render_task_line(task: dict[str, Any]) -> str:
    """Render a single task as a Markdown checkbox line."""
    status = task.get("status", "needsAction")
    checkbox = "[x]" if status == "completed" else "[ ]"
    title = task.get("title") or "Untitled"
    parts = [f"- {checkbox} {title}"]

    due = task.get("due")
    if due:
        parts.append(f" (due: {due})")

    return "".join(parts)


def _render_tasklist_markdown(
    tasklist: dict[str, Any],
    tasks: list[dict[str, Any]],
) -> str:
    """Render a Google Tasks list and its tasks as Markdown."""
    title = tasklist.get("title") or "Untitled List"
    lines = [f"# {title}", ""]

    active = [t for t in tasks if t.get("status") != "completed"]
    completed = [t for t in tasks if t.get("status") == "completed"]

    if active:
        lines.append(f"## Active ({len(active)})")
        lines.append("")
        for task in active:
            lines.append(_render_task_line(task))
            notes = (task.get("notes") or "").strip()
            if notes:
                for note_line in notes.split("\n"):
                    lines.append(f"  > {note_line}")
        lines.append("")

    if completed:
        lines.append(f"## Completed ({len(completed)})")
        lines.append("")
        for task in completed:
            lines.append(_render_task_line(task))
        lines.append("")

    return "\n".join(lines)


def resolve_google_tasks_credentials(
    *,
    user_id: str | None = None,
    namespace: str | None = None,
) -> tuple[Credentials, dict[str, Any]]:
    """Resolve Google OAuth credentials for Tasks access.

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


class GoogleTasksImporter:
    """Fetch Google Tasks and upsert them into Alfred's document store."""

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

        self.connector = GoogleTasksConnector(
            credentials,
            user_id=user_id,
            on_credentials_refreshed=_on_refresh,
        )

    async def import_task_lists(
        self,
        *,
        doc_store: DocStorageService,
        include_completed: bool = True,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Import Google Tasks lists into Alfred's document store.

        Args:
            doc_store: Alfred document storage service.
            include_completed: Whether to include completed tasks.
            limit: Maximum number of task lists to import (None = unlimited).

        Returns:
            Summary dict with counts and document mapping.
        """
        task_lists, error = await self.connector.list_task_lists()
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

        for tasklist in task_lists:
            if limit is not None and (created + updated) >= limit:
                break

            tasklist_id = tasklist.get("id")
            if not tasklist_id:
                skipped += 1
                continue

            try:
                tasks, task_error = await self.connector.list_tasks(
                    tasklist_id,
                    show_completed=include_completed,
                    show_hidden=include_completed,
                )
                if task_error:
                    errors.append({"tasklist_id": tasklist_id, "error": task_error})
                    continue

                if not tasks:
                    skipped += 1
                    continue

                title = tasklist.get("title") or "Untitled List"
                markdown = _render_tasklist_markdown(tasklist, tasks)
                cleaned_text = markdown.strip()

                source_url = f"https://tasks.google.com/task/{tasklist_id}"
                stable_hash = f"gtasks:{tasklist_id}"

                active_count = sum(1 for t in tasks if t.get("status") != "completed")
                completed_count = sum(1 for t in tasks if t.get("status") == "completed")

                gtasks_meta = {
                    "tasklist_id": tasklist_id,
                    "tasklist_title": title,
                    "updated": tasklist.get("updated"),
                    "active_task_count": active_count,
                    "completed_task_count": completed_count,
                }

                ingest = DocumentIngest(
                    source_url=source_url,
                    title=title,
                    content_type="google_tasks",
                    raw_markdown=markdown,
                    cleaned_text=cleaned_text,
                    hash=stable_hash,
                    metadata={"source": "google_tasks", "google_tasks": gtasks_meta},
                )

                res = doc_store.ingest_document_store_only(ingest)
                doc_id = str(res["id"])

                if res.get("duplicate"):
                    try:
                        doc_store.update_document_text(
                            doc_id,
                            title=title,
                            cleaned_text=cleaned_text,
                            raw_markdown=markdown,
                            metadata_update={"source": "google_tasks", "google_tasks": gtasks_meta},
                        )
                        updated += 1
                    except Exception:
                        logger.debug("Skipping update for duplicate %s", doc_id)
                        skipped += 1
                else:
                    created += 1

                documents.append({"tasklist_id": tasklist_id, "document_id": doc_id})

            except Exception as exc:
                logger.exception("Google Tasks import failed for list %s", tasklist_id)
                errors.append({"tasklist_id": str(tasklist_id), "error": str(exc)})

        return {
            "ok": True,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "documents": documents,
        }


def import_google_tasks(
    *,
    doc_store: DocStorageService,
    user_id: str | None = None,
    namespace: str | None = None,
    include_completed: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    """Convenience wrapper to import Google Tasks into the document store.

    This is the main entry point for callers. It resolves credentials, creates the
    importer, and runs the async import in a synchronous context.

    Args:
        doc_store: Alfred document storage service.
        user_id: Optional user identifier for token lookup.
        namespace: Optional namespace for token storage partitioning.
        include_completed: Whether to include completed tasks.
        limit: Maximum number of task lists to import.

    Returns:
        Summary dict with counts, document mapping, and token info.
    """
    creds, token_info = resolve_google_tasks_credentials(
        user_id=user_id, namespace=namespace
    )
    importer = GoogleTasksImporter(
        credentials=creds, user_id=user_id, namespace=namespace
    )

    # Run the async import - use existing event loop if available, otherwise create one
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(
                asyncio.run,
                importer.import_task_lists(
                    doc_store=doc_store,
                    include_completed=include_completed,
                    limit=limit,
                ),
            ).result()
    else:
        result = asyncio.run(
            importer.import_task_lists(
                doc_store=doc_store,
                include_completed=include_completed,
                limit=limit,
            )
        )

    result["token"] = token_info
    return result


__all__ = [
    "GoogleTasksImporter",
    "import_google_tasks",
    "resolve_google_tasks_credentials",
]
