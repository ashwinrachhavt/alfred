"""Helpers for turning web scrapes into structured capture metadata."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+[^)]*)\)")
_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+[^)]*)\)")


def _first_str(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def detect_platform(url: str, metadata: dict[str, Any] | None = None) -> str | None:
    """Best-effort platform detection from URL and Firecrawl metadata."""

    host = _domain(url)
    source = _first_str((metadata or {}).get("sourceURL"), (metadata or {}).get("url")) or ""
    combined = f"{host} {source}".lower()
    if "substack" in combined or host.endswith("edge.ceo"):
        return "substack"
    if "medium.com" in combined:
        return "medium"
    if "github.com" in combined:
        return "github"
    if "arxiv.org" in combined:
        return "arxiv"
    return None


def extract_headings(markdown: str, *, limit: int = 80) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for match in _HEADING_RE.finditer(markdown or ""):
        text = re.sub(r"\s+", " ", match.group(2)).strip(" #")
        if text:
            headings.append({"level": len(match.group(1)), "text": text})
        if len(headings) >= limit:
            break
    return headings


def extract_images(markdown: str, *, limit: int = 50) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    for index, match in enumerate(_IMAGE_RE.finditer(markdown or "")):
        images.append(
            {
                "url": match.group(2).strip(),
                "alt": match.group(1).strip(),
                "position": index,
            }
        )
        if len(images) >= limit:
            break
    return images


def extract_links(markdown: str, *, limit: int = 100) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for index, match in enumerate(_LINK_RE.finditer(markdown or "")):
        links.append(
            {
                "url": match.group(2).strip(),
                "text": match.group(1).strip(),
                "position": index,
            }
        )
        if len(links) >= limit:
            break
    return links


def classify_page_kind(*, url: str, metadata: dict[str, Any] | None, markdown: str) -> str:
    """Classify captured pages with deterministic, cheap rules."""

    meta = metadata or {}
    host = _domain(url)
    title = (_first_str(meta.get("og:title"), meta.get("title")) or "").lower()
    og_type = (_first_str(meta.get("og:type"), meta.get("ogType")) or "").lower()
    text = f"{url} {host} {title} {markdown[:2000]}".lower()

    if "arxiv.org" in host or "/pdf/" in text or "abstract" in title:
        return "paper"
    if "twitter.com" in host or "x.com" in host or "reddit.com" in host:
        return "social_thread"
    if "docs." in host or "/docs/" in text or "api reference" in text or "sdk docs" in text:
        return "documentation"
    if (
        "chapter" in title
        or "/chapter" in text
        or re.search(r"^#\s+chapter\s+\d+", markdown, re.I | re.M)
    ):
        return "chapter"
    if (
        og_type == "article"
        or "/p/" in urlparse(url).path
        or detect_platform(url, meta) in {"substack", "medium"}
    ):
        return "blog_article"
    if any(word in text for word in ("pricing", "customers", "sign up", "book a demo")):
        return "product_page"
    return "generic_page"


def build_source_capture(
    *,
    url: str,
    markdown: str,
    html: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize Firecrawl output into durable document metadata."""

    _ = html
    meta = metadata or {}
    kind = classify_page_kind(url=url, metadata=meta, markdown=markdown)
    title = _first_str(
        meta.get("og:title"),
        meta.get("ogTitle"),
        meta.get("twitter:title"),
        meta.get("title"),
    )
    subtitle = _first_str(
        meta.get("description"),
        meta.get("og:description"),
        meta.get("ogDescription"),
        meta.get("twitter:description"),
    )
    canonical_url = _first_str(
        meta.get("og:url"),
        meta.get("ogUrl"),
        meta.get("url"),
        meta.get("sourceURL"),
        url,
    )
    cover = _first_str(
        meta.get("og:image"),
        meta.get("ogImage"),
        meta.get("twitter:image"),
        meta.get("image"),
    )
    return {
        "kind": kind,
        "platform": detect_platform(url, meta),
        "title": title,
        "subtitle": subtitle,
        "author": _first_str(meta.get("author"), meta.get("article:author")),
        "published_at": _first_str(
            meta.get("article:published_time"),
            meta.get("publishedTime"),
            meta.get("date"),
        ),
        "canonical_url": canonical_url,
        "cover_image_url": cover,
        "headings": extract_headings(markdown),
        "images": extract_images(markdown),
        "links": extract_links(markdown),
        "firecrawl": {
            "scrape_id": meta.get("scrapeId"),
            "status_code": meta.get("statusCode"),
            "content_type": meta.get("contentType"),
        },
    }


def apply_image_rewrite_map(
    source_capture: dict[str, Any], rewrite_map: dict[str, str]
) -> dict[str, Any]:
    """Attach local asset URLs to source capture image metadata."""

    updated = dict(source_capture or {})
    images = []
    for image in updated.get("images") or []:
        if isinstance(image, dict):
            next_image = dict(image)
            if next_image.get("url") in rewrite_map:
                next_image["local_url"] = rewrite_map[next_image["url"]]
            images.append(next_image)
    updated["images"] = images
    cover = updated.get("cover_image_url")
    if isinstance(cover, str) and cover in rewrite_map:
        updated["cover_image_url"] = rewrite_map[cover]
    return updated


def build_document_chat_context(doc: dict[str, Any], *, max_chars: int = 6000) -> str:
    """Build a bounded source context block for document-scoped Q&A."""

    metadata = doc.get("metadata") or {}
    source_capture = metadata.get("source_capture") if isinstance(metadata, dict) else {}
    if not isinstance(source_capture, dict):
        source_capture = {}

    enrichment = doc.get("enrichment") if isinstance(doc.get("enrichment"), dict) else {}
    source_analysis = enrichment.get("source_analysis") if isinstance(enrichment, dict) else {}
    if not isinstance(source_analysis, dict):
        source_analysis = {}

    summary = doc.get("summary") if isinstance(doc.get("summary"), dict) else {}
    headings = source_capture.get("headings") or []
    heading_text = "\n".join(
        f"{'#' * int(item.get('level', 2))} {item.get('text')}"
        for item in headings[:12]
        if isinstance(item, dict) and item.get("text")
    )
    argument_flow = source_analysis.get("argument_flow") or []
    if not isinstance(argument_flow, list):
        argument_flow = []

    parts = [
        f"Document: {doc.get('title') or 'Untitled'}",
        f"Source: {doc.get('source_url') or doc.get('canonical_url') or ''}",
        f"Kind: {source_capture.get('kind') or doc.get('content_type') or 'web'}",
        f"Author: {source_capture.get('author') or ''}",
        f"Summary: {summary.get('short') or ''}",
        f"Thesis: {source_analysis.get('thesis') or ''}",
        "Argument flow: " + "; ".join(str(item) for item in argument_flow),
        "Headings:\n" + heading_text,
        "Excerpt:\n" + (doc.get("cleaned_text") or "")[:2500],
    ]
    context = "\n".join(part for part in parts if part.strip() and not part.endswith(": "))
    return context[:max_chars]
