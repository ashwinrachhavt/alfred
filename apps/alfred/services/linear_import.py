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
from alfred.schemas.imports import CONTENT_TYPE_LINEAR_ISSUE, ImportStats
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


def import_linear(
    *,
    doc_store: DocStorageService,
    token: str | None = None,
    limit: int | None = None,
    since: str | datetime | None = None,
) -> dict[str, Any]:
    """Import Linear issues into Alfred's document store.

    Args:
        doc_store: The document storage service.
        token: Optional explicit Linear API token.
        limit: Max number of issues to import.
        since: ISO date (YYYY-MM-DD) or datetime for incremental sync.
              When provided, only issues created/updated since that date
              are fetched.
    """
    resolved_token = _resolve_token(token)
    connector = LinearConnector(token=resolved_token)

    effective_limit = limit if limit is not None else 100

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
                return {
                    "ok": True,
                    "created": 0,
                    "updated": 0,
                    "skipped": 0,
                    "errors": [{"error": error}],
                    "documents": [],
                }
    else:
        issues = connector.get_all_issues(include_comments=True, limit=effective_limit)

    stats = ImportStats()

    for issue in issues:
        identifier = issue.get("identifier")
        if not identifier:
            stats.skipped += 1
            continue

        try:
            formatted = connector.format_issue(issue)
            markdown = connector.format_issue_to_markdown(formatted)
            cleaned_text = markdown.strip()
            title = f"{formatted.get('identifier', '')}: {formatted.get('title', '')}".strip()

            source_url = f"https://linear.app/issue/{identifier}"
            stable_hash = f"linear:{identifier}"

            # Extract tags from labels if present
            labels = issue.get("labels", {})
            label_nodes = labels.get("nodes", []) if isinstance(labels, dict) else []
            tag_names = [lbl.get("name") for lbl in label_nodes if lbl.get("name")]

            linear_meta: dict[str, Any] = {
                "identifier": identifier,
                "issue_id": issue.get("id"),
                "state": formatted.get("state"),
                "state_type": formatted.get("state_type"),
                "assignee": formatted.get("assignee", {}).get("name") if formatted.get("assignee") else None,
                "creator": formatted.get("creator", {}).get("name") if formatted.get("creator") else None,
                "created_at": formatted.get("created_at"),
                "updated_at": formatted.get("updated_at"),
                "num_comments": len(formatted.get("comments", [])),
            }

            ingest = DocumentIngest(
                source_url=source_url,
                title=title,
                content_type=CONTENT_TYPE_LINEAR_ISSUE,
                raw_markdown=markdown,
                cleaned_text=cleaned_text,
                hash=stable_hash,
                tags=tag_names or None,
                metadata={"source": "linear", "linear": linear_meta},
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
                        metadata_update={"source": "linear", "linear": linear_meta},
                    )
                    stats.updated += 1
                except Exception:
                    logger.debug("Skipping update for duplicate %s", doc_id)
                    stats.skipped += 1
            else:
                stats.created += 1

            stats.documents.append({"identifier": identifier, "document_id": doc_id})

        except Exception as exc:
            logger.exception("Linear import failed for issue %s", identifier)
            stats.errors.append({"identifier": str(identifier), "error": str(exc)})

    return stats.to_dict()


__all__ = ["import_linear"]
