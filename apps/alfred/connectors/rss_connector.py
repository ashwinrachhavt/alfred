"""RSS/Atom feed connector for Alfred.

Fetches and parses RSS 2.0 and Atom feeds using httpx and xml.etree.ElementTree.
No external feed-parsing dependency required.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from alfred.core.settings import settings

logger = logging.getLogger(__name__)

# Atom namespace
_ATOM_NS = "http://www.w3.org/2005/Atom"
# content:encoded namespace (RSS 2.0 extension)
_CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"


class RSSClient:
    """Sync client for fetching and parsing RSS/Atom feeds."""

    def __init__(
        self,
        *,
        timeout_seconds: int = 30,
        user_agent: str | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._user_agent = user_agent or settings.user_agent
        self._headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        }

    def fetch_feed(self, url: str) -> dict[str, Any]:
        """Fetch and parse an RSS/Atom feed.

        Returns::

            {
                "title": str,
                "link": str,
                "entries": [
                    {
                        "title": str,
                        "link": str,
                        "published": str | None,
                        "summary": str | None,
                        "content": str | None,
                        "author": str | None,
                        "categories": list[str],
                    },
                    ...
                ],
            }
        """
        resp = httpx.get(url, headers=self._headers, timeout=self._timeout, follow_redirects=True)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)

        # Detect format
        if root.tag == "rss" or root.tag.endswith("}rss"):
            return self._parse_rss2(root, url)
        if root.tag == f"{{{_ATOM_NS}}}feed" or root.tag == "feed":
            return self._parse_atom(root, url)

        # Fallback: check for <channel> child (some feeds omit <rss> wrapper)
        channel = root.find("channel")
        if channel is not None:
            return self._parse_rss2(root, url)

        raise ValueError(f"Unrecognised feed format: root tag is <{root.tag}>")

    def fetch_multiple(self, urls: list[str]) -> list[dict[str, Any]]:
        """Fetch multiple feeds, returning a list of parsed feed dicts.

        Feeds that fail to fetch or parse are logged and skipped.
        """
        results: list[dict[str, Any]] = []
        for url in urls:
            try:
                results.append(self.fetch_feed(url))
            except Exception:
                logger.exception("Failed to fetch/parse feed: %s", url)
        return results

    # ------------------------------------------------------------------
    # RSS 2.0
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_rss2(root: ET.Element, feed_url: str) -> dict[str, Any]:
        channel = root.find("channel")
        if channel is None:
            channel = root  # degenerate case

        feed_title = _text(channel, "title") or feed_url
        feed_link = _text(channel, "link") or feed_url

        entries: list[dict[str, Any]] = []
        for item in channel.iter("item"):
            content_encoded = _text(item, f"{{{_CONTENT_NS}}}encoded")
            entries.append(
                {
                    "title": _text(item, "title") or "",
                    "link": _text(item, "link") or "",
                    "published": _text(item, "pubDate"),
                    "summary": _text(item, "description"),
                    "content": content_encoded,
                    "author": _text(item, "author"),
                    "categories": [
                        cat.text.strip()
                        for cat in item.findall("category")
                        if cat.text and cat.text.strip()
                    ],
                }
            )

        return {"title": feed_title, "link": feed_link, "entries": entries}

    # ------------------------------------------------------------------
    # Atom
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_atom(root: ET.Element, feed_url: str) -> dict[str, Any]:
        ns = _ATOM_NS
        ns_prefix = f"{{{ns}}}"

        # Some feeds use default namespace, some don't
        def _find(el: ET.Element, tag: str) -> ET.Element | None:
            return el.find(f"{ns_prefix}{tag}") or el.find(tag)

        def _findall(el: ET.Element, tag: str) -> list[ET.Element]:
            return el.findall(f"{ns_prefix}{tag}") or el.findall(tag)

        def _find_text(el: ET.Element, tag: str) -> str | None:
            child = _find(el, tag)
            return child.text.strip() if child is not None and child.text else None

        # Feed-level
        feed_title = _find_text(root, "title") or feed_url

        feed_link = feed_url
        for link_el in _findall(root, "link"):
            rel = link_el.get("rel", "alternate")
            if rel == "alternate":
                feed_link = link_el.get("href", feed_url)
                break

        entries: list[dict[str, Any]] = []
        for entry in _findall(root, "entry"):
            # Link
            entry_link = ""
            for link_el in _findall(entry, "link"):
                rel = link_el.get("rel", "alternate")
                if rel == "alternate":
                    entry_link = link_el.get("href", "")
                    break
            if not entry_link:
                # Fallback: first link with href
                for link_el in _findall(entry, "link"):
                    href = link_el.get("href")
                    if href:
                        entry_link = href
                        break

            # Content
            content_el = _find(entry, "content")
            content = content_el.text.strip() if content_el is not None and content_el.text else None

            # Author
            author_el = _find(entry, "author")
            author = None
            if author_el is not None:
                author = _find_text(author_el, "name")

            # Categories
            categories = [
                cat.get("term", "").strip()
                for cat in _findall(entry, "category")
                if cat.get("term", "").strip()
            ]

            entries.append(
                {
                    "title": _find_text(entry, "title") or "",
                    "link": entry_link,
                    "published": _find_text(entry, "published") or _find_text(entry, "updated"),
                    "summary": _find_text(entry, "summary"),
                    "content": content,
                    "author": author,
                    "categories": categories,
                }
            )

        return {"title": feed_title, "link": feed_link, "entries": entries}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _text(parent: ET.Element, tag: str) -> str | None:
    """Return stripped text of a direct child element, or None."""
    el = parent.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return None


__all__ = ["RSSClient"]
