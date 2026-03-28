"""Ingest Linear issues into Alfred's document store.

Each issue becomes a single document rendered as Markdown using the
connector's built-in formatter. Supports incremental sync via date range
filtering and deduplication via stable hash ``linear:{identifier}``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from alfred.connectors.linear_connector import LinearConnector
from alfred.core.settings import settings
from alfred.schemas.documents import DocumentIngest
from alfred.schemas.imports import CONTENT_TYPE_LINEAR_ISSUE
from alfred.services.base_import import BaseImportService
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


def _resolve_token(token: str | None) -> str:
    """Resolve a Linear API token from the explicit argument or settings."""
    if token:
        return token
    if settings.linear_api_key:
        value = settings.linear_api_key.get_secret_value()
        if value and value.strip():
            return value.strip()
    raise ValueError(
        "No Linear API token provided. Pass token= or set LINEAR_API_KEY."
    )


class LinearImportService(BaseImportService):
    """Import Linear issues into Alfred's document store."""

    def __init__(
        self,
        *,
        doc_store: DocStorageService,
        token: str | None = None,
        limit: int | None = None,
    ) -> None:
        super().__init__(doc_store=doc_store, source_name="linear")
        self._token = token
        self._limit = limit

    def fetch_items(self, *, since: datetime | str | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        resolved_token = _resolve_token(self._token)
        connector = LinearConnector(token=resolved_token)
        effective_limit = self._limit if self._limit is not None else 100

        if since:
            start_date = since if isinstance(since, str) else since.strftime("%Y-%m-%d")
            end_date = datetime.now(UTC).strftime("%Y-%m-%d")
            issues, error = connector.get_issues_by_date_range(
                start_date=start_date,
                end_date=end_date,
                include_comments=True,
                limit=effective_limit,
            )
            if error:
                logger.warning("Linear date-range fetch returned error: %s", error)
                if not issues:
                    return []
        else:
            issues = connector.get_all_issues(include_comments=True, limit=effective_limit)

        # Stash connector on each item so map_to_document can format
        for issue in issues:
            issue["_connector"] = connector
        return issues

    def map_to_document(self, item: dict[str, Any]) -> DocumentIngest:
        connector: LinearConnector = item.pop("_connector")
        identifier = item.get("identifier", "")

        formatted = connector.format_issue(item)
        markdown = connector.format_issue_to_markdown(formatted)
        title = f"{formatted.get('identifier', '')}: {formatted.get('title', '')}".strip()

        labels = item.get("labels", {})
        label_nodes = labels.get("nodes", []) if isinstance(labels, dict) else []
        tag_names = [lbl.get("name") for lbl in label_nodes if lbl.get("name")]

        linear_meta: dict[str, Any] = {
            "identifier": identifier,
            "issue_id": item.get("id"),
            "state": formatted.get("state"),
            "state_type": formatted.get("state_type"),
            "assignee": formatted.get("assignee", {}).get("name") if formatted.get("assignee") else None,
            "creator": formatted.get("creator", {}).get("name") if formatted.get("creator") else None,
            "created_at": formatted.get("created_at"),
            "updated_at": formatted.get("updated_at"),
            "num_comments": len(formatted.get("comments", [])),
        }

        return DocumentIngest(
            source_url=f"https://linear.app/issue/{identifier}",
            title=title,
            content_type=CONTENT_TYPE_LINEAR_ISSUE,
            raw_markdown=markdown,
            cleaned_text=markdown.strip(),
            hash=f"linear:{identifier}",
            tags=tag_names or None,
            metadata={"source": "linear", "linear": linear_meta},
        )

    def item_id(self, item: dict[str, Any]) -> str:
        return str(item.get("identifier", "unknown"))


def import_linear(
    *,
    doc_store: DocStorageService,
    token: str | None = None,
    limit: int | None = None,
    since: str | datetime | None = None,
) -> dict[str, Any]:
    """Convenience wrapper preserving the existing function signature."""
    svc = LinearImportService(doc_store=doc_store, token=token, limit=limit)
    return svc.run_import(since=since)


__all__ = ["LinearImportService", "import_linear"]
