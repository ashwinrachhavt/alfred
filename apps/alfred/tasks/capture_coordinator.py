"""Capture coordinator: sequences post-ingest tasks before the main pipeline.

Solves the pipeline race condition: ingest_document_store_only() fires the
pipeline immediately, but image download and Firecrawl enrichment need to
mutate raw_markdown BEFORE chunking/enrichment runs.

Flow:
  1. Firecrawl re-scrape for source structure and richer markdown
  2. Download images from markdown, rewrite URLs, and update metadata
  3. Dispatch the main enrichment pipeline
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from celery import shared_task

from alfred.connectors.firecrawl_connector import FirecrawlClient
from alfred.services.web_capture import apply_image_rewrite_map, build_source_capture

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
    force_firecrawl: bool = False,
    user_id: str = "",
) -> dict[str, Any]:
    """Coordinate post-ingest processing before the main pipeline."""
    results: dict[str, Any] = {"doc_id": doc_id, "steps_completed": []}

    # Step 1: Rich web capture via Firecrawl when requested by the extension,
    # or for generic web pages where local extraction is usually lossy.
    should_firecrawl = (
        force_firecrawl
        or (source_url.startswith("http") and content_type_hint == "generic")
    )
    if should_firecrawl and source_url.startswith("http"):
        try:
            upgraded = _firecrawl_enrich(doc_id, source_url, force=force_firecrawl)
            results["firecrawl"] = "upgraded" if upgraded else "kept_original"
            results["steps_completed"].append("firecrawl")
        except Exception:
            _mark_rich_capture_status(doc_id, "error")
            logger.warning("Firecrawl enrichment failed for %s, continuing", doc_id, exc_info=True)

    # Step 2: Special content type handling if Firecrawl was not already forced.
    elif content_type_hint in ("youtube", "github", "arxiv", "twitter"):
        try:
            _handle_special_content(doc_id, source_url, content_type_hint)
            results["steps_completed"].append("special_extraction")
        except Exception:
            logger.warning("Special extraction failed for %s, continuing", doc_id, exc_info=True)

    # Step 3: Download images after Firecrawl, so the task captures assets from
    # the rich scrape instead of only the extension's local fallback markdown.
    if has_images or _document_has_markdown_images(doc_id):
        try:
            from alfred.tasks.image_download import download_document_images

            img_result = download_document_images(doc_id)
            results["image_download"] = img_result
            rewrite_map = img_result.get("rewrite_map") if isinstance(img_result, dict) else None
            if isinstance(rewrite_map, dict) and rewrite_map:
                _apply_asset_rewrite_metadata(doc_id, rewrite_map)
            results["steps_completed"].append("image_download")
        except Exception:
            logger.warning("Image download failed for %s, continuing", doc_id, exc_info=True)

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
        _firecrawl_enrich(doc_id, source_url, force=True)


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


def _firecrawl_enrich(doc_id: str, source_url: str, *, force: bool = False) -> bool:
    """Re-scrape URL via Firecrawl. Returns True if document was upgraded."""
    from sqlmodel import select

    from alfred.core.database import get_db_session
    from alfred.models.doc_storage import DocumentRow

    fc = FirecrawlClient()
    resp = fc.scrape_rich(source_url)
    if not resp.success or not resp.markdown or len(resp.markdown.strip()) < 50:
        _mark_rich_capture_status(doc_id, "failed")
        return False

    firecrawl_md = resp.markdown.strip()
    source_capture = build_source_capture(
        url=source_url,
        markdown=firecrawl_md,
        html=getattr(resp, "html", None),
        metadata=getattr(resp, "metadata", None),
    )

    session = get_db_session()
    try:
        doc = session.exec(select(DocumentRow).where(DocumentRow.id == uuid.UUID(doc_id))).first()
        if not doc:
            return False

        existing_md = (doc.raw_markdown or "").strip()
        should_upgrade = (
            force
            or not existing_md
            or len(firecrawl_md) > len(existing_md) * 1.2
            or firecrawl_md.count("![") > existing_md.count("![") + 2
        )

        meta = dict(doc.meta or {})
        capture_meta = dict(meta.get("capture") or {})
        capture_meta["rich_capture_status"] = "complete"
        meta["capture"] = capture_meta
        meta["source_capture"] = source_capture
        doc.meta = meta

        if source_capture.get("title"):
            doc.title = str(source_capture["title"])
        if source_capture.get("canonical_url"):
            doc.canonical_url = str(source_capture["canonical_url"])

        if should_upgrade:
            doc.raw_markdown = firecrawl_md
            doc.cleaned_text = firecrawl_md
            session.add(doc)
            session.commit()
            return True
        session.add(doc)
        session.commit()
        return False
    finally:
        session.close()


def _document_has_markdown_images(doc_id: str) -> bool:
    from sqlmodel import select

    from alfred.core.database import get_db_session
    from alfred.models.doc_storage import DocumentRow

    session = get_db_session()
    try:
        raw_markdown = session.exec(
            select(DocumentRow.raw_markdown).where(DocumentRow.id == uuid.UUID(doc_id))
        ).first()
        return bool(raw_markdown and "![" in raw_markdown)
    finally:
        session.close()


def _apply_asset_rewrite_metadata(doc_id: str, rewrite_map: dict[str, str]) -> None:
    from sqlmodel import select

    from alfred.core.database import get_db_session
    from alfred.models.doc_storage import DocumentRow

    session = get_db_session()
    try:
        doc = session.exec(select(DocumentRow).where(DocumentRow.id == uuid.UUID(doc_id))).first()
        if not doc:
            return
        meta = dict(doc.meta or {})
        source_capture = meta.get("source_capture")
        if not isinstance(source_capture, dict):
            return
        meta["source_capture"] = apply_image_rewrite_map(source_capture, rewrite_map)
        doc.meta = meta
        session.add(doc)
        session.commit()
    finally:
        session.close()


def _mark_rich_capture_status(doc_id: str, status: str) -> None:
    from sqlmodel import select

    from alfred.core.database import get_db_session
    from alfred.models.doc_storage import DocumentRow

    session = get_db_session()
    try:
        doc = session.exec(select(DocumentRow).where(DocumentRow.id == uuid.UUID(doc_id))).first()
        if not doc:
            return
        meta = dict(doc.meta or {})
        capture_meta = dict(meta.get("capture") or {})
        capture_meta["rich_capture_status"] = status
        meta["capture"] = capture_meta
        doc.meta = meta
        session.add(doc)
        session.commit()
    finally:
        session.close()
