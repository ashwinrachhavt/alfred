"""Ingest Todoist projects and tasks into Alfred's document store.

Each project becomes a single document containing all its tasks rendered as
Markdown. Supports importing active tasks and optionally completed tasks.
"""

from __future__ import annotations

import logging
from typing import Any

from alfred.connectors.todoist_connector import TodoistClient
from alfred.schemas.documents import DocumentIngest
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


def _priority_label(priority: int) -> str:
    """Convert Todoist priority (1-4, where 4 is highest) to a label."""
    return {4: "P1", 3: "P2", 2: "P3", 1: "P4"}.get(priority, "")


def _render_task_line(task: dict[str, Any], *, completed: bool = False) -> str:
    """Render a single task as a Markdown checkbox line."""
    checkbox = "[x]" if completed else "[ ]"
    content = task.get("content") or task.get("task_id") or "Untitled"
    parts = [f"- {checkbox} {content}"]

    priority = task.get("priority")
    if priority and priority > 1:
        parts.append(f" `{_priority_label(priority)}`")

    due = task.get("due")
    if due:
        due_date = due.get("date") if isinstance(due, dict) else str(due)
        if due_date:
            parts.append(f" (due: {due_date})")

    return "".join(parts)


def _render_task_description(task: dict[str, Any]) -> list[str]:
    """Render the description and comments for a task as indented lines."""
    lines: list[str] = []
    description = (task.get("description") or "").strip()
    if description:
        for desc_line in description.split("\n"):
            lines.append(f"  > {desc_line}")
    return lines


def _render_project_markdown(
    project: dict[str, Any],
    tasks: list[dict[str, Any]],
    completed_tasks: list[dict[str, Any]] | None = None,
) -> str:
    """Render a Todoist project and its tasks as Markdown."""
    name = project.get("name") or "Untitled Project"
    lines = [f"# {name}", ""]

    if tasks:
        lines.append(f"## Active Tasks ({len(tasks)})")
        lines.append("")
        for task in tasks:
            lines.append(_render_task_line(task))
            lines.extend(_render_task_description(task))
        lines.append("")

    if completed_tasks:
        lines.append(f"## Completed Tasks ({len(completed_tasks)})")
        lines.append("")
        for task in completed_tasks:
            lines.append(_render_task_line(task, completed=True))
        lines.append("")

    return "\n".join(lines)


def import_todoist(
    *,
    doc_store: DocStorageService,
    token: str | None = None,
    project_id: str | None = None,
    include_completed: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """Import Todoist projects and tasks into Alfred's document store.

    Each project is imported as a single document containing all its tasks.

    Args:
        doc_store: The document storage service.
        token: Optional explicit Todoist API token.
        project_id: Optional project ID to import only one project.
        include_completed: Whether to also fetch completed tasks.
        limit: Max number of projects to import.
    """
    client = TodoistClient(token=token)

    projects = client.list_projects()
    if project_id:
        projects = [p for p in projects if str(p.get("id")) == project_id]

    if limit is not None:
        projects = projects[:limit]

    created = 0
    updated = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    documents: list[dict[str, str]] = []

    for project in projects:
        pid = str(project.get("id", ""))
        if not pid:
            skipped += 1
            continue

        try:
            tasks = client.list_tasks(project_id=pid)

            completed_tasks: list[dict[str, Any]] | None = None
            if include_completed:
                completed_tasks = client.list_completed_tasks(project_id=pid)

            if not tasks and not (completed_tasks or []):
                skipped += 1
                continue

            name = project.get("name") or "Untitled Project"
            markdown = _render_project_markdown(project, tasks, completed_tasks)
            cleaned_text = markdown.strip()

            source_url = project.get("url") or f"todoist://project/{pid}"
            stable_hash = f"todoist:project:{pid}"

            # Collect all unique labels from tasks
            all_labels: list[str] = []
            for task in tasks:
                for label in task.get("labels") or []:
                    if label not in all_labels:
                        all_labels.append(label)

            todoist_meta = {
                "project_id": pid,
                "project_name": name,
                "color": project.get("color"),
                "is_favorite": project.get("is_favorite"),
                "active_task_count": len(tasks),
                "completed_task_count": len(completed_tasks) if completed_tasks else 0,
            }

            ingest = DocumentIngest(
                source_url=source_url,
                title=name,
                content_type="todoist_project",
                raw_markdown=markdown,
                cleaned_text=cleaned_text,
                hash=stable_hash,
                tags=all_labels or None,
                metadata={"source": "todoist", "todoist": todoist_meta},
            )

            res = doc_store.ingest_document_store_only(ingest)
            doc_id = str(res["id"])

            if res.get("duplicate"):
                updated += 1
                doc_store.update_document_text(
                    doc_id,
                    title=name,
                    cleaned_text=cleaned_text,
                    raw_markdown=markdown,
                    metadata_update={"source": "todoist", "todoist": todoist_meta},
                )
            else:
                created += 1

            documents.append({"project_id": pid, "document_id": doc_id})

        except Exception as exc:
            logger.exception("Todoist import failed for project %s", pid)
            errors.append({"project_id": pid, "error": str(exc)})

    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "documents": documents,
    }


__all__ = ["import_todoist"]
