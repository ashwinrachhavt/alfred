from __future__ import annotations

from urllib.parse import quote


def inline_content_disposition(filename: str | None, *, fallback: str = "asset") -> str:
    """Build a browser-safe inline Content-Disposition header for Unicode filenames."""
    raw = (filename or fallback).strip() or fallback
    safe = raw.replace("\\", "_").replace("/", "_").replace("\r", "_").replace("\n", "_")
    ascii_name = safe.encode("ascii", "ignore").decode("ascii").replace('"', "_")
    if not ascii_name:
        ascii_name = fallback
    encoded = quote(safe, safe="")
    return f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"
