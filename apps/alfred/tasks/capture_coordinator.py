"""Capture coordinator: sequences post-ingest tasks before the main pipeline.

Solves the pipeline race condition: ingest_document_store_only() fires the
pipeline immediately, but image download and Firecrawl enrichment need to
mutate raw_markdown BEFORE chunking/enrichment runs.

Flow:
  1. Download images from markdown, rewrite URLs (if images present)
  2. Firecrawl re-scrape for quality enrichment (generic pages only)
  3. Dispatch the main enrichment pipeline
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name="alfred.tasks.capture_coordinator.coordinate_capture",
    bind=True,
    max_retries=1,
)
def coordinate_capture(
    self,
    doc_id: str,
    source_url: str = "",
    has_images: bool = False,
    content_type_hint: str = "generic",
    user_id: str = "",
) -> dict[str, Any]:
    """Coordinate post-ingest processing before the main pipeline."""
    results: dict[str, Any] = {"doc_id": doc_id, "steps_completed": []}

    # Step 1: Download images
    if has_images:
        try:
            from alfred.tasks.image_download import download_document_images
            img_result = download_document_images(doc_id)
            results["image_download"] = img_result
            results["steps_completed"].append("image_download")
        except Exception:
            logger.warning("Image download failed for %s, continuing", doc_id, exc_info=True)

    # Step 2: Special content type handling
    if content_type_hint in ("youtube", "github", "arxiv", "twitter"):
        try:
            _handle_special_content(doc_id, source_url, content_type_hint)
            results["steps_completed"].append("special_extraction")
        except Exception:
            logger.warning("Special extraction failed for %s, continuing", doc_id, exc_info=True)

    # Step 3: Firecrawl enrichment (generic pages only)
    elif source_url and source_url.startswith("http") and content_type_hint == "generic":
        try:
            upgraded = _firecrawl_enrich(doc_id, source_url)
            results["firecrawl"] = "upgraded" if upgraded else "kept_original"
            results["steps_completed"].append("firecrawl")
        except Exception:
            logger.warning("Firecrawl enrichment failed for %s, continuing", doc_id, exc_info=True)

    # Step 4: Dispatch main pipeline
    try:
        from alfred.tasks.document_pipeline import run_document_pipeline
        run_document_pipeline.delay(doc_id=doc_id, user_id=user_id)
        results["steps_completed"].append("pipeline_dispatch")
    except Exception:
        logger.warning("Failed to dispatch pipeline for %s", doc_id, exc_info=True)

    return results


def _handle_special_content(doc_id: str, source_url: str, content_type: str) -> None:
    """Route special content types to appropriate backend extractors."""
    if content_type == "github":
        _enrich_github(doc_id, source_url)
    elif content_type == "arxiv":
        _enrich_arxiv(doc_id, source_url)
    elif content_type in ("youtube", "twitter"):
        _firecrawl_enrich(doc_id, source_url)


def _enrich_github(doc_id: str, source_url: str) -> None:
    """Fetch raw markdown from GitHub."""
    import httpx
    from sqlmodel import select

    from alfred.core.database import get_db_session
    from alfred.models.doc_storage import DocumentRow

    raw_url = None
    blob_match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)", source_url)
    if blob_match:
        owner, repo, branch, path = blob_match.groups()
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"

    repo_match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?$", source_url)
    if not raw_url and repo_match:
        owner, repo = repo_match.groups()
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md"

    if not raw_url:
        return

    resp = httpx.get(raw_url, timeout=15, follow_redirects=True)
    resp.raise_for_status()
    markdown = resp.text
    if len(markdown.strip()) < 50:
        return

    session = get_db_session()
    try:
        doc = session.exec(select(DocumentRow).where(DocumentRow.id == uuid.UUID(doc_id))).first()
        if doc:
            doc.raw_markdown = markdown
            doc.cleaned_text = markdown
            session.add(doc)
            session.commit()
    finally:
        session.close()


def _enrich_arxiv(doc_id: str, source_url: str) -> None:
    """Extract arXiv abstract and metadata."""
    import httpx
    from sqlmodel import select

    from alfred.core.database import get_db_session
    from alfred.models.doc_storage import DocumentRow

    arxiv_match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+)", source_url)
    if not arxiv_match:
        return

    arxiv_id = arxiv_match.group(1)
    abs_url = f"https://arxiv.org/abs/{arxiv_id}"

    resp = httpx.get(abs_url, timeout=15, follow_redirects=True)
    resp.raise_for_status()
    html = resp.text

    title_match = re.search(r'<h1 class="title mathjax">\s*<span[^>]*>Title:</span>\s*(.*?)</h1>', html, re.DOTALL)
    abstract_match = re.search(r'<blockquote class="abstract mathjax">\s*<span[^>]*>Abstract:</span>\s*(.*?)</blockquote>', html, re.DOTALL)
    authors_match = re.search(r'<div class="authors">\s*<span[^>]*>Authors:</span>\s*(.*?)</div>', html, re.DOTALL)

    title = title_match.group(1).strip() if title_match else ""
    abstract = abstract_match.group(1).strip() if abstract_match else ""
    authors = re.sub(r"<[^>]+>", "", authors_match.group(1).strip()) if authors_match else ""

    if not abstract:
        return

    markdown = f"# {title}\n\n**Authors:** {authors}\n\n**arXiv:** [{arxiv_id}]({abs_url})\n\n## Abstract\n\n{abstract}\n"

    session = get_db_session()
    try:
        doc = session.exec(select(DocumentRow).where(DocumentRow.id == uuid.UUID(doc_id))).first()
        if doc:
            doc.raw_markdown = markdown
            if title:
                doc.title = title
            session.add(doc)
            session.commit()
    finally:
        session.close()


def _firecrawl_enrich(doc_id: str, source_url: str) -> bool:
    """Re-scrape URL via Firecrawl. Returns True if document was upgraded."""
    from sqlmodel import select

    from alfred.connectors.firecrawl_connector import FirecrawlClient
    from alfred.core.database import get_db_session
    from alfred.models.doc_storage import DocumentRow

    fc = FirecrawlClient()
    resp = fc.scrape(source_url)
    if not resp.success or not resp.markdown or len(resp.markdown.strip()) < 50:
        return False

    firecrawl_md = resp.markdown.strip()

    session = get_db_session()
    try:
        doc = session.exec(select(DocumentRow).where(DocumentRow.id == uuid.UUID(doc_id))).first()
        if not doc:
            return False

        existing_md = (doc.raw_markdown or "").strip()
        should_upgrade = (
            len(firecrawl_md) > len(existing_md) * 1.2
            or firecrawl_md.count("![") > existing_md.count("![") + 2
        )

        if should_upgrade:
            doc.raw_markdown = firecrawl_md
            doc.cleaned_text = firecrawl_md
            session.add(doc)
            session.commit()
            return True
        return False
    finally:
        session.close()
