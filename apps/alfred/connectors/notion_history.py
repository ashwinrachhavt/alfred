"""Async Notion history connector for Alfred.

- Uses AsyncClient and proper pagination for search + block children.
- Respects repo config via `settings.notion_token`.
- Supports optional date filtering on `last_edited_time`.
- Produces a clean, recursive structure suitable for indexing / RAG.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from notion_client import AsyncClient
from notion_client.errors import APIResponseError

from alfred.core.config import settings

logger = logging.getLogger(__name__)


def _parse_iso(dt: str | datetime | None) -> Optional[datetime]:
    """Parse an ISO 8601 string or datetime into an aware datetime (UTC)."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    # Notion returns e.g. "2025-01-01T12:34:56.789Z"
    dt = dt.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(dt)
    except Exception:
        logger.warning("Failed to parse datetime from %r", dt)
        return None


async def _enumerate_async(
    iterable: AsyncIterator[Dict[str, Any]],
) -> AsyncIterator[Tuple[int, Dict[str, Any]]]:
    index = 0
    async for item in iterable:
        yield index, item
        index += 1


class NotionHistoryConnector:
    """Fetch full-page content (including nested blocks) from Notion."""

    def __init__(
        self,
        token: Optional[str] = None,
        page_size: int = 50,
    ) -> None:
        """
        Args:
            token: Optional explicit Notion token. If omitted, uses settings.notion_token.
            page_size: Page size for search queries (clamped to 1–100).
        """
        self._token = token or settings.notion_token
        if not self._token:
            raise RuntimeError("NOTION_TOKEN is not configured")

        self.client = AsyncClient(auth=self._token)
        self.page_size = max(1, min(100, page_size))

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> "NotionHistoryConnector":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    # ------------------------
    # High-level public API
    # ------------------------

    async def get_all_pages(
        self,
        start_date: Optional[str | datetime] = None,
        end_date: Optional[str | datetime] = None,
        limit: Optional[int] = None,
        include_content: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all pages shared with the integration, including nested blocks.

        Args:
            start_date: Filter pages with last_edited_time >= this (ISO string or datetime).
            end_date:   Filter pages with last_edited_time <= this (ISO string or datetime).

        Returns:
            List of page dicts:
            {
              "page_id": str,
              "title": str,
              "content": [ <block-tree> ],
              "last_edited_time": str | None,
            }
        """
        start_dt = _parse_iso(start_date) if start_date else None
        end_dt = _parse_iso(end_date) if end_date else None

        results: List[Dict[str, Any]] = []

        async for index, page in _enumerate_async(
            self._iter_pages(start_dt=start_dt, end_dt=end_dt)
        ):
            page_id = page["id"]
            last_edited_raw = page.get("last_edited_time")

            content = None
            if include_content:
                content = await self.get_page_content(page_id)

            results.append(
                {
                    "page_id": page_id,
                    "title": self.get_page_title(page),
                    "content": content,
                    "last_edited_time": last_edited_raw,
                }
            )

            if limit is not None and limit >= 0 and (index + 1) >= limit:
                break

        return results

    async def get_page_content(self, page_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all blocks (and nested children) for a page.

        Returns:
            List of block dicts:
            {
              "id": str,
              "type": str,
              "content": str,
              "children": [ ...same shape... ],
            }
        """
        # Top-level blocks (fully paginated)
        root_blocks = await self._fetch_all_children(page_id)

        processed: List[Dict[str, Any]] = []
        for block in root_blocks:
            processed.append(await self._process_block(block))

        return processed

    # ------------------------
    # Internal helpers
    # ------------------------

    async def _iter_pages(
        self,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Async generator over all pages the integration can see, paginated.
        Applies last_edited_time filtering client-side.
        """
        search_params: Dict[str, Any] = {
            "filter": {"value": "page", "property": "object"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            "page_size": self.page_size,
        }

        cursor: Optional[str] = None

        while True:
            if cursor:
                search_params["start_cursor"] = cursor
            else:
                search_params.pop("start_cursor", None)

            try:
                resp = await self.client.search(**search_params)
            except APIResponseError as e:
                logger.exception("Notion search failed: %s", e)
                raise
            except Exception as e:  # network / serialization, etc.
                logger.exception("Unexpected error during Notion search: %s", e)
                raise

            if not isinstance(resp, dict):
                raise RuntimeError(f"Unexpected Notion search response type: {type(resp)}")

            pages = resp.get("results", []) or []
            for page in pages:
                last_edited = _parse_iso(page.get("last_edited_time"))
                if start_dt and last_edited and last_edited < start_dt:
                    continue
                if end_dt and last_edited and last_edited > end_dt:
                    continue
                yield page

            if not resp.get("has_more"):
                break

            cursor = resp.get("next_cursor")
            if not cursor:
                break

    async def _fetch_all_children(self, block_id: str) -> List[Dict[str, Any]]:
        """Fetch all children for a block/page, handling pagination."""
        items: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        while True:
            kwargs: Dict[str, Any] = {"block_id": block_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor

            try:
                resp = await self.client.blocks.children.list(**kwargs)
            except APIResponseError as e:
                logger.exception("Notion blocks.children.list failed: %s", e)
                raise
            except Exception as e:
                logger.exception("Unexpected error in blocks.children.list: %s", e)
                raise

            if not isinstance(resp, dict):
                raise RuntimeError(f"Unexpected blocks.children.list response type: {type(resp)}")

            items.extend(resp.get("results", []) or [])

            if not resp.get("has_more"):
                break

            cursor = resp.get("next_cursor")
            if not cursor:
                break

        return items

    async def _process_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """Process a block and recursively process all children."""
        block_id = block["id"]
        block_type = block["type"]

        content = self._extract_block_content(block)

        children: List[Dict[str, Any]] = []
        if block.get("has_children"):
            for child in await self._fetch_all_children(block_id):
                children.append(await self._process_block(child))

        return {
            "id": block_id,
            "type": block_type,
            "content": content,
            "children": children,
        }

    # ------------------------
    # Content extraction
    # ------------------------

    def get_page_title(self, page: Dict[str, Any]) -> str:
        """Extract a human-readable title from a page object."""
        properties = page.get("properties", {}) or {}
        for _name, prop in properties.items():
            if prop.get("type") == "title":
                fragments = prop.get("title", []) or []
                if fragments:
                    return " ".join(f.get("plain_text", "") for f in fragments).strip()
        return f"Untitled page ({page['id']})"

    def _extract_block_content(self, block: Dict[str, Any]) -> str:
        """
        Extract readable content from a Notion block.

        Returns plain text / simple markdown suitable for indexing.
        """
        block_type = block.get("type")
        data = block.get(block_type, {}) or {}

        # Generic rich_text blocks
        rich = data.get("rich_text")
        if isinstance(rich, list):
            return "".join(fragment.get("plain_text", "") for fragment in rich)

        # Images (sanitized)
        if block_type == "image":
            image_data = block.get("image", {}) or {}
            if "file" in image_data:
                # Notion-hosted images (presigned S3 URLs) – do not leak the URL.
                return "[Notion Image]"
            if "external" in image_data:
                from urllib.parse import urlparse

                url = image_data["external"].get("url", "")
                try:
                    parsed = urlparse(url)
                    host = parsed.netloc or "external"
                    return f"[External Image from {host}]"
                except Exception:
                    return "[External Image]"

        # Code blocks
        if block_type == "code":
            lang = data.get("language", "plain")
            code_rich = data.get("rich_text", []) or []
            code_text = "".join(frag.get("plain_text", "") for frag in code_rich)
            return f"```{lang}\n{code_text}\n```"

        # Equations
        if block_type == "equation":
            return data.get("expression", "")

        # Fallback: nothing useful
        return ""
