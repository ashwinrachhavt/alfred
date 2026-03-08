"""Ingest Notion workspace content into Alfred's document store.

This module focuses on a pragmatic MVP:
- Import all accessible pages via Notion Search API
- Fetch full block trees for each page
- Render blocks to Markdown (no media downloads yet)
- Upsert into Alfred `documents` using a stable hash: `notion:{page_id}`

It supports two auth modes:
- `NOTION_TOKEN` (legacy/internal integration token)
- Notion OAuth tokens stored via `alfred.services.notion_oauth`
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from notion_client import Client
from notion_client.errors import APIResponseError
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from alfred.core.exceptions import ConfigurationError
from alfred.core.settings import settings
from alfred.schemas.documents import DocumentIngest
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.notion_markdown import NotionMarkdownRenderer
from alfred.services.notion_oauth import list_connected_workspaces, load_oauth_token

logger = logging.getLogger(__name__)


def _parse_iso(dt: str | datetime | None) -> datetime | None:
    """Parse a Notion ISO datetime into an aware datetime (UTC)."""

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


def resolve_notion_access_token(*, workspace_id: str | None = None) -> tuple[str, dict[str, Any]]:
    """Resolve an access token from env config or stored OAuth tokens."""

    if settings.notion_token is not None and settings.notion_token.get_secret_value().strip():
        return settings.notion_token.get_secret_value(), {"source": "env"}

    if workspace_id:
        token = load_oauth_token(workspace_id)
        access_token = (token.get("access_token") or "").strip()
        if not access_token:
            raise ConfigurationError("Stored Notion OAuth token missing access_token.")
        return access_token, {"source": "oauth", "workspace_id": workspace_id}

    workspaces = list_connected_workspaces()
    if len(workspaces) == 1:
        wid = workspaces[0]["workspace_id"]
        token = load_oauth_token(wid)
        access_token = (token.get("access_token") or "").strip()
        if not access_token:
            raise ConfigurationError("Stored Notion OAuth token missing access_token.")
        return access_token, {"source": "oauth", "workspace_id": wid}

    if not workspaces:
        raise ConfigurationError(
            "No Notion token configured. Set NOTION_TOKEN or connect via Notion OAuth."
        )

    raise ConfigurationError(
        "Multiple Notion workspaces connected. Provide a workspace_id to select one."
    )


class NotionPageImporter:
    """Fetch Notion pages and upsert them into Alfred documents."""

    def __init__(
        self,
        *,
        access_token: str,
        page_size: int = 100,
        sleep_s: float = 0.35,
        renderer: NotionMarkdownRenderer | None = None,
    ) -> None:
        self.client = Client(auth=access_token)
        self.page_size = max(1, min(100, int(page_size)))
        self.sleep_s = max(0.0, float(sleep_s))
        self.renderer = renderer or NotionMarkdownRenderer()

    def import_workspace(
        self,
        *,
        doc_store: DocStorageService,
        limit: int | None = None,
        since: str | datetime | None = None,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        """Import pages from Notion into Alfred's document store."""

        since_dt = _parse_iso(since) if since else None
        created = 0
        updated = 0
        skipped = 0
        errors: list[dict[str, str]] = []
        documents: list[dict[str, str]] = []

        for page in self._iter_pages(
            limit=limit, since=since_dt, include_archived=include_archived
        ):
            page_id = page.get("id")
            if not page_id:
                skipped += 1
                continue

            try:
                title = self.renderer.page_title(page)
                blocks = self._fetch_block_tree(page_id)
                markdown = self.renderer.render_blocks(blocks)
                cleaned_text = markdown.strip() or title

                source_url = (page.get("url") or f"notion://{page_id}").strip()
                stable_hash = f"notion:{page_id}"

                notion_meta = {
                    "page_id": page_id,
                    "url": page.get("url"),
                    "created_time": page.get("created_time"),
                    "last_edited_time": page.get("last_edited_time"),
                    "archived": bool(page.get("archived", False)),
                    "in_trash": bool(page.get("in_trash", False)),
                    "parent": page.get("parent"),
                }

                ingest = DocumentIngest(
                    source_url=source_url,
                    title=title,
                    content_type="notion",
                    raw_markdown=markdown,
                    cleaned_text=cleaned_text,
                    hash=stable_hash,
                    metadata={"source": "notion", "notion": notion_meta},
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
                            metadata_update={"source": "notion", "notion": notion_meta},
                        )
                        updated += 1
                    except Exception:
                        logger.debug("Skipping update for duplicate %s", doc_id)
                        skipped += 1
                else:
                    created += 1

                documents.append({"page_id": page_id, "document_id": doc_id})
            except Exception as exc:  # pragma: no cover - network/runtime dependent
                logger.exception("Notion import failed for %s", page_id)
                errors.append({"page_id": str(page_id), "error": str(exc)})

        return {
            "ok": True,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "documents": documents,
        }

    # ------------------------
    # Notion API wrappers
    # ------------------------

    def _sleep(self) -> None:
        if self.sleep_s > 0:
            time.sleep(self.sleep_s)

    @retry(wait=wait_exponential_jitter(1, 5), stop=stop_after_attempt(5))
    def _search(self, **payload: Any) -> dict[str, Any]:
        self._sleep()
        return self.client.search(**payload)

    @retry(wait=wait_exponential_jitter(1, 5), stop=stop_after_attempt(5))
    def _list_children(self, *, block_id: str, start_cursor: str | None = None) -> dict[str, Any]:
        self._sleep()
        kwargs: dict[str, Any] = {"block_id": block_id, "page_size": 100}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor
        return self.client.blocks.children.list(**kwargs)

    def _iter_pages(
        self,
        *,
        limit: int | None,
        since: datetime | None,
        include_archived: bool,
    ) -> Iterator[dict[str, Any]]:
        remaining = None if limit is None else max(0, int(limit))
        cursor: str | None = None

        while True:
            payload: dict[str, Any] = {
                "filter": {"value": "page", "property": "object"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"},
                "page_size": self.page_size,
            }
            if cursor:
                payload["start_cursor"] = cursor

            try:
                resp = self._search(**payload)
            except APIResponseError as exc:
                raise RuntimeError(
                    f"Notion search failed: {getattr(exc, 'message', str(exc))}"
                ) from exc

            results = resp.get("results", []) or []
            for page in results:
                if remaining is not None and remaining <= 0:
                    return

                if not include_archived and (page.get("archived") or page.get("in_trash")):
                    continue

                last_edited = _parse_iso(page.get("last_edited_time"))
                if since and last_edited and last_edited < since:
                    # Search results are sorted by last_edited_time desc.
                    return

                yield page
                if remaining is not None:
                    remaining -= 1

            if not resp.get("has_more"):
                return
            cursor = resp.get("next_cursor")
            if not cursor:
                return

    def _fetch_block_tree(self, block_id: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            resp = self._list_children(block_id=block_id, start_cursor=cursor)
            blocks.extend(resp.get("results", []) or [])
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
            if not cursor:
                break

        for block in blocks:
            if block.get("has_children"):
                child_id = block.get("id")
                if child_id:
                    block["children"] = self._fetch_block_tree(child_id)
                else:
                    block["children"] = []

        return blocks


def import_notion_workspace(
    *,
    doc_store: DocStorageService,
    workspace_id: str | None = None,
    limit: int | None = None,
    since: str | datetime | None = None,
    include_archived: bool = False,
    sleep_s: float = 0.35,
) -> dict[str, Any]:
    """Convenience wrapper to import a Notion workspace into the document store."""

    access_token, token_info = resolve_notion_access_token(workspace_id=workspace_id)
    importer = NotionPageImporter(access_token=access_token, sleep_s=sleep_s)
    result = importer.import_workspace(
        doc_store=doc_store, limit=limit, since=since, include_archived=include_archived
    )
    result["token"] = token_info
    return result


__all__ = [
    "NotionPageImporter",
    "import_notion_workspace",
    "resolve_notion_access_token",
]
