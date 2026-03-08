"""Shared helpers for the Postgres-backed document storage service.

These functions are intentionally side-effect free and safe to import in tests.
"""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse

from alfred.core.exceptions import BadRequestError
from alfred.core.utils import clamp_int


def token_count(text: str) -> int:
    """Return a rough token count suitable for chunk sizing."""

    return len((text or "").split())


def parse_uuid(value: str | None) -> uuid.UUID | None:
    """Parse a UUID string; returns None when invalid."""

    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


def parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 datetime string; returns None when invalid."""

    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_iso_date(value: str | None) -> date | None:
    """Parse an ISO-8601 datetime/date string and return the date component."""

    dt = parse_iso_datetime(value)
    return dt.date() if dt else None


def read_text_file_best_effort(path: str | None) -> str | None:
    """Read a UTF-8 text file; returns None on any filesystem error."""

    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def sha256_hex(text: str) -> str:
    """Compute a stable SHA-256 hex digest for the given text."""

    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def excerpt_for_cover_prompt(text: str | None, *, max_chars: int = 900) -> str | None:
    """Return a compact excerpt suitable for an image prompt.

    Used for "visual grounding" so the cover reflects the actual document.
    Keep it short to reduce prompt size and limit accidental prompt injection surface.
    """

    if not text:
        return None
    s = " ".join((text or "").strip().split())
    if not s:
        return None
    max_chars = max(120, min(int(max_chars), 4000))
    if len(s) <= max_chars:
        return s
    # Reserve space for an ellipsis.
    return (s[: max_chars - 1].rstrip() + "…") if max_chars > 1 else "…"


def start_of_day_utc(dt: datetime) -> date:
    """Return the UTC day bucket for a datetime."""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).date()


def domain_from_url(url: str | None) -> str | None:
    """Extract a domain (netloc) from a URL, best-effort."""

    if not url:
        return None
    try:
        return urlparse(url).netloc or None
    except Exception:
        return None


def apply_offset_limit(stmt, *, skip: int, limit: int, max_limit: int = 200):
    """Apply offset/limit with clamping."""

    return stmt.offset(int(skip)).limit(clamp_int(limit, lo=1, hi=max_limit))


def first_str(*candidates: Any) -> str | None:
    """Return the first non-empty string among candidates."""

    for c in candidates:
        if isinstance(c, str):
            s = c.strip()
            if s:
                return s
    return None


def best_effort_title(*, row_title: str | None, meta: dict[str, Any] | None) -> str:
    """Pick a user-facing title from structured metadata."""

    meta = meta or {}
    title = first_str(
        meta.get("title"),
        meta.get("page_title"),
        meta.get("name"),
        row_title,
    )
    return title or "Untitled"


def best_effort_cover_url(meta: dict[str, Any] | None) -> str | None:
    """Pick a cover image URL from structured metadata."""

    meta = meta or {}
    return first_str(
        meta.get("image"),
        meta.get("image_url"),
        meta.get("cover"),
        meta.get("cover_image"),
        meta.get("thumbnail"),
        meta.get("thumbnail_url"),
    )


def best_effort_primary_topic(
    topics: dict[str, Any] | None,
    meta: dict[str, Any] | None,
) -> str | None:
    """Extract a primary topic from persisted topics and enrichment payloads."""

    topics = topics or {}
    meta = meta or {}

    primary = topics.get("primary")
    if isinstance(primary, str) and primary.strip():
        return primary.strip()

    cls = topics.get("classification")
    if isinstance(cls, dict):
        for key in ("primary_topic", "primary", "topic", "category"):
            val = cls.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

    enrichment = meta.get("enrichment")
    if isinstance(enrichment, dict):
        topics2 = enrichment.get("topics")
        if isinstance(topics2, dict):
            val = topics2.get("primary")
            if isinstance(val, str) and val.strip():
                return val.strip()

    return None


def build_title_image_prompt(
    *,
    title: str,
    summary: str | None,
    primary_topic: str | None,
    domain: str | None,
    excerpt: str | None = None,
    visual_brief: str | None = None,
) -> str:
    """Build an image-generation prompt for a document cover.

    The goal is a timeless, clean cover image that works well in a library UI.
    """

    title = (title or "").strip() or "Untitled"
    summary = (summary or "").strip() or None
    primary_topic = (primary_topic or "").strip() or None
    domain = (domain or "").strip() or None
    excerpt = (excerpt or "").strip() or None
    visual_brief = (visual_brief or "").strip() or None

    context_parts: list[str] = []
    if primary_topic:
        context_parts.append(f"Primary topic: {primary_topic}.")
    if domain:
        context_parts.append(f"Source domain: {domain}.")
    if summary:
        context_parts.append(f"Summary: {summary}.")
    if excerpt:
        context_parts.append(f"Excerpt (for visual grounding): {excerpt}.")
    if visual_brief:
        context_parts.append(f"Visual brief: {visual_brief}.")

    context = "\n".join(context_parts)
    if context:
        context = f"\n{context}\n"

    return (
        "Create a high-quality, modern editorial illustration to be used as a cover image for a saved article.\n"
        f"Article title: {title}\n"
        f"{context}"
        "Constraints:\n"
        "- Do not include any text, lettering, watermarks, logos, or UI.\n"
        "- Avoid clutter; keep the composition minimal and readable at small sizes.\n"
        "- Use a tasteful color palette and crisp shapes; slightly abstract is fine.\n"
        "Output: a single image.\n"
    )


def encode_cursor(*, created_at: datetime, doc_id: str) -> str:
    """Encode a stable, opaque cursor for pagination."""

    payload = {"created_at": created_at.isoformat(), "id": doc_id}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    """Decode a cursor produced by `encode_cursor`.

    Raises:
        BadRequestError: When the cursor is missing or malformed.
    """

    if not cursor:
        raise BadRequestError("cursor must not be empty", code="invalid_cursor")

    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise BadRequestError("Invalid cursor", code="invalid_cursor") from exc

    if not isinstance(payload, dict):
        raise BadRequestError("Invalid cursor", code="invalid_cursor")

    created_at_raw = payload.get("created_at")
    doc_id = payload.get("id")
    if not isinstance(created_at_raw, str) or not isinstance(doc_id, str):
        raise BadRequestError("Invalid cursor", code="invalid_cursor")

    try:
        created_at = datetime.fromisoformat(created_at_raw)
    except Exception as exc:
        raise BadRequestError("Invalid cursor", code="invalid_cursor") from exc
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    return created_at, doc_id


__all__ = [
    "apply_offset_limit",
    "best_effort_cover_url",
    "best_effort_primary_topic",
    "best_effort_title",
    "build_title_image_prompt",
    "decode_cursor",
    "domain_from_url",
    "encode_cursor",
    "excerpt_for_cover_prompt",
    "first_str",
    "parse_iso_date",
    "parse_iso_datetime",
    "parse_uuid",
    "read_text_file_best_effort",
    "sha256_hex",
    "start_of_day_utc",
    "token_count",
]
