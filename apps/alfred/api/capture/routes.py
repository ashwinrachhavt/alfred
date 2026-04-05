"""Universal capture endpoint.

Accepts raw text or URLs, auto-detects content type, and feeds into
the existing document enrichment pipeline. Returns immediately.
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from alfred.core.dependencies import get_doc_storage_service
from alfred.schemas.documents import DocumentIngest
from alfred.services.doc_storage import DocStorageService

router = APIRouter(prefix="/api/capture", tags=["capture"])
logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(
    r"^https?://[^\s]+$"
    r"|^(youtube\.com|arxiv\.org|twitter\.com|x\.com|github\.com|medium\.com"
    r"|notion\.so|substack\.com|reddit\.com)[^\s]*$",
    re.IGNORECASE,
)


class CaptureRequest(BaseModel):
    content: str
    tags: list[str] | None = None
    source: str = "web-app"


class CaptureResponse(BaseModel):
    id: str
    status: str  # "accepted" | "duplicate" | "scraping"
    content_type: str  # "url" | "text"


def _is_url(text: str) -> bool:
    """Check if the entire input (trimmed) looks like a URL."""
    stripped = text.strip()
    if URL_PATTERN.match(stripped):
        return True
    # Also match bare domains with paths
    if re.match(r"^[\w.-]+\.\w{2,}/", stripped):
        return True
    return False


def _normalize_url(text: str) -> str:
    """Add https:// if missing."""
    stripped = text.strip()
    if not stripped.startswith(("http://", "https://")):
        return f"https://{stripped}"
    return stripped


@router.post("", response_model=CaptureResponse, status_code=status.HTTP_201_CREATED)
def capture(
    payload: CaptureRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> CaptureResponse:
    """Universal capture: paste text or URL, Alfred handles the rest.

    For URLs: scrapes via Firecrawl, then enriches.
    For text: creates document directly, then enriches.
    Both paths fire the full pipeline (extract → decompose → embed → link).
    """
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Content is required")
    if len(content) < 10:
        raise HTTPException(status_code=400, detail="Content too short (min 10 chars)")

    metadata = {"source": payload.source}

    if _is_url(content):
        url = _normalize_url(content)
        return _capture_url(url, tags=payload.tags, metadata=metadata, svc=svc)
    else:
        return _capture_text(content, tags=payload.tags, metadata=metadata, svc=svc)


def _capture_url(
    url: str,
    *,
    tags: list[str] | None,
    metadata: dict,
    svc: DocStorageService,
) -> CaptureResponse:
    """Scrape URL via Firecrawl, then ingest into pipeline."""
    # Try Firecrawl first for rich content extraction
    scraped_text = None
    title = None
    try:
        from alfred.connectors.firecrawl_connector import FirecrawlClient

        fc = FirecrawlClient()
        resp = fc.scrape(url)
        if resp.success and resp.markdown:
            scraped_text = resp.markdown
            title = resp.data.get("title") if isinstance(resp.data, dict) else None
    except Exception:
        logger.warning("Firecrawl scrape failed for %s, falling back to URL-only", url)

    ingest = DocumentIngest(
        source_url=url,
        title=title or url,
        cleaned_text=scraped_text or f"Captured URL: {url}",
        content_type="web",
        tags=tags,
        metadata=metadata,
    )
    res = svc.ingest_document_store_only(ingest)

    if res.get("duplicate"):
        return CaptureResponse(id=res["id"], status="duplicate", content_type="url")

    return CaptureResponse(id=res["id"], status="accepted", content_type="url")


def _capture_text(
    text: str,
    *,
    tags: list[str] | None,
    metadata: dict,
    svc: DocStorageService,
) -> CaptureResponse:
    """Ingest raw text directly into pipeline."""
    # Extract title from first line
    first_line = text.split("\n", 1)[0].strip()
    title = first_line[:120] if first_line else "Untitled capture"

    ingest = DocumentIngest(
        source_url="capture://web-app",
        title=title,
        cleaned_text=text,
        content_type="note",
        tags=tags,
        metadata=metadata,
    )
    res = svc.ingest_document_store_only(ingest)

    if res.get("duplicate"):
        return CaptureResponse(id=res["id"], status="duplicate", content_type="text")

    return CaptureResponse(id=res["id"], status="accepted", content_type="text")
