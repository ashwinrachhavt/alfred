from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from alfred.core.celery_client import get_celery_client
from alfred.core.dependencies import get_doc_storage_service
from alfred.core.exceptions import AlfredException
from alfred.schemas.documents import (
    DocumentDetailsResponse,
    DocumentIngest,
    DocumentTextUpdateRequest,
    ExplorerDocumentsResponse,
    NoteCreate,
    NoteCreateRequest,
    NoteResponse,
    NotesListResponse,
    SemanticMapResponse,
)
from alfred.services.doc_storage_pg import DocStorageService

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)


@router.post(
    "/notes",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    payload: NoteCreateRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> NoteResponse:
    try:
        note_id = svc.create_note(
            NoteCreate(text=payload.text, source_url=payload.source_url, metadata=payload.metadata)
        )
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        raise HTTPException(status_code=500, detail="Failed to create note") from exc

    note = svc.get_note(note_id)
    if not note:
        raise HTTPException(status_code=500, detail="Note not found after creation")
    return NoteResponse(**note)


@router.get(
    "/notes",
    response_model=NotesListResponse,
)
def list_notes(
    q: str | None = Query(None, description="Optional text search"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> NotesListResponse:
    try:
        data = svc.list_notes(q=q, skip=skip, limit=limit)
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        raise HTTPException(status_code=500, detail="Failed to list notes") from exc

    return NotesListResponse(
        items=[NoteResponse(**item) for item in data["items"]],
        total=data["total"],
        skip=data["skip"],
        limit=data["limit"],
    )


# Back-compat: page, doc, search (aliased under documents)
class PageRequest(BaseModel):
    raw_text: str = Field(..., min_length=50)
    html: str | None = None
    page_url: str | None = None
    page_title: str | None = None
    selection_type: Literal["full_page", "selection", "article_only"] = "full_page"


class PageResponse(BaseModel):
    id: str
    status: str
    task_id: str | None = None
    status_url: str | None = None


class DocumentTitleImageRequest(BaseModel):
    model: str = Field(default="gpt-image-1", description="OpenAI image model to use.")
    size: str = Field(default="1024x1024", description="Requested output size.")
    quality: str = Field(default="high", description="Requested output quality.")


class DocumentTitleImageResponse(BaseModel):
    id: str
    status: str
    cover_image_url: str | None = None
    skipped: bool = False
    reason: str | None = None


@router.post("/page/extract", response_model=PageResponse)
def create_page(
    payload: PageRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> PageResponse:
    try:
        cleaned_text = (payload.raw_text or "").strip()
        ingest = DocumentIngest(
            source_url=(payload.page_url or "about:blank"),
            title=payload.page_title,
            cleaned_text=cleaned_text,
            content_type="web",
        )
        res = svc.ingest_document_store_only(ingest)
        if res.get("duplicate"):
            return PageResponse(id=res["id"], status="duplicate")
        try:
            celery_client = get_celery_client()
            async_result = celery_client.send_task(
                "alfred.tasks.document_processing.process",
                kwargs={"doc_id": res["id"], "force": False},
            )
            return PageResponse(
                id=res["id"],
                status="queued",
                task_id=async_result.id,
                status_url=f"/tasks/{async_result.id}",
            )
        except Exception:  # pragma: no cover - external IO
            logger.exception("Failed to enqueue document processing for %s", res["id"])
            return PageResponse(id=res["id"], status="stored")
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Page extract ingestion failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to ingest page") from exc


@router.post("/doc/{id}/enrich", response_model=PageResponse)
def enqueue_document_enrichment(
    id: str,
    force: bool = Query(False, description="Force enrichment even if already present"),
) -> PageResponse:
    """Enqueue asynchronous enrichment for a stored document."""

    try:
        celery_client = get_celery_client()
        async_result = celery_client.send_task(
            "alfred.tasks.document_enrichment.enrich",
            kwargs={"doc_id": id, "force": force},
        )
        return PageResponse(
            id=id,
            status="queued",
            task_id=async_result.id,
            status_url=f"/tasks/{async_result.id}",
        )
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Failed to enqueue document enrichment: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to enqueue enrichment") from exc


class FetchOrganizeResponse(BaseModel):
    id: str
    status: str
    tokens: int | None = None
    task_id: str | None = None


@router.post("/doc/{id}/fetch-and-organize", response_model=FetchOrganizeResponse)
def fetch_and_organize(
    id: str,
    force: bool = Query(False, description="Re-fetch even if content exists"),
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> FetchOrganizeResponse:
    """Fetch full page content from source URL via Firecrawl, store as clean
    markdown, then trigger enrichment.

    Use when the captured content is too short (e.g. selection or RSS snippet)
    and the source URL has the full article.
    """
    try:
        doc = svc.get_document_details(id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Skip if already has substantial content (unless forced)
        existing_text = doc.get("cleaned_text") or ""
        _MIN_SUBSTANTIAL_CONTENT_LEN = 500
        if not force and len(existing_text) > _MIN_SUBSTANTIAL_CONTENT_LEN:
            return FetchOrganizeResponse(id=id, status="already_has_content", tokens=doc.get("tokens"))

        source_url = doc.get("source_url") or doc.get("canonical_url")
        if not source_url or source_url.startswith("about:"):
            raise HTTPException(status_code=400, detail="No source URL to fetch from")

        # Scrape the page via Firecrawl
        from alfred.connectors.firecrawl_connector import FirecrawlClient

        fc = FirecrawlClient()
        result = fc.scrape(source_url)

        if not result.success or not result.markdown:
            raise HTTPException(status_code=502, detail=f"Failed to fetch page: {result.error}")

        markdown = result.markdown.strip()
        _MIN_FETCH_CONTENT_LEN = 50
        if len(markdown) < _MIN_FETCH_CONTENT_LEN:
            raise HTTPException(status_code=422, detail="Fetched content too short")

        # Update the document with the full markdown content
        svc.update_document_text(
            id,
            raw_markdown=markdown,
            cleaned_text=markdown,
        )

        # Trigger enrichment
        try:
            celery_client = get_celery_client()
            async_result = celery_client.send_task(
                "alfred.tasks.document_enrichment.enrich",
                kwargs={"doc_id": id, "force": True},
            )
            return FetchOrganizeResponse(
                id=id,
                status="fetched_and_enriching",
                tokens=len(markdown.split()),
                task_id=async_result.id,
            )
        except Exception:
            return FetchOrganizeResponse(
                id=id,
                status="fetched",
                tokens=len(markdown.split()),
            )

    except HTTPException:
        raise
    except AlfredException:
        raise
    except Exception as exc:
        logger.exception("Fetch and organize failed for %s: %s", id, exc)
        raise HTTPException(status_code=500, detail="Failed to fetch and organize") from exc


@router.get("/{id}/image")
def get_document_image(
    id: str,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> Response:
    """Fetch the stored cover image for a document (PNG)."""

    try:
        img = svc.get_document_image_bytes(id)
        if not img:
            raise HTTPException(status_code=404, detail="Image not found")
        return Response(
            content=img,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except HTTPException:
        raise
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Failed to fetch document image: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch image") from exc


@router.post("/{id}/image", response_model=DocumentTitleImageResponse)
def generate_document_image(
    id: str,
    force: bool = Query(False, description="Regenerate even if already present"),
    payload: DocumentTitleImageRequest = Body(default_factory=DocumentTitleImageRequest),
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> DocumentTitleImageResponse:
    """Generate and persist a cover image for a document synchronously."""

    try:
        res = svc.generate_document_title_image(
            id,
            force=force,
            model=payload.model,
            size=payload.size,
            quality=payload.quality,
        )
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Failed to generate document image: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate image") from exc

    skipped = bool(res.get("skipped"))
    return DocumentTitleImageResponse(
        id=id,
        status="skipped" if skipped else "generated",
        cover_image_url=f"/api/documents/{id}/image",
        skipped=skipped,
        reason=res.get("reason"),
    )


@router.post("/{id}/image/async", response_model=PageResponse)
def enqueue_document_image_generation(
    id: str,
    force: bool = Query(False, description="Regenerate even if already present"),
    payload: DocumentTitleImageRequest = Body(default_factory=DocumentTitleImageRequest),
) -> PageResponse:
    """Enqueue asynchronous title-image generation for a stored document."""

    try:
        celery_client = get_celery_client()
        async_result = celery_client.send_task(
            "alfred.tasks.document_title_image.generate",
            kwargs={
                "doc_id": id,
                "force": force,
                "model": payload.model,
                "size": payload.size,
                "quality": payload.quality,
            },
        )
        return PageResponse(
            id=id,
            status="queued",
            task_id=async_result.id,
            status_url=f"/tasks/{async_result.id}",
        )
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Failed to enqueue document image generation: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to enqueue image generation") from exc


@router.get("/doc/{id}")
def get_document(
    id: str,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> dict:
    try:
        doc = svc.get_document(id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc
    except HTTPException:
        raise
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        raise HTTPException(status_code=500, detail="Failed to fetch document") from exc


@router.get("/{id}/details", response_model=DocumentDetailsResponse)
def get_document_details(
    id: str,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> dict:
    try:
        doc = svc.get_document_details(id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc
    except HTTPException:
        raise
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Failed to fetch document details for %s", id)
        raise HTTPException(status_code=500, detail=f"Failed: {type(exc).__name__}: {exc}") from exc


@router.patch("/{id}/text", response_model=DocumentDetailsResponse)
def update_document_text(
    id: str,
    payload: DocumentTextUpdateRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> dict:
    try:
        updated = svc.update_document_text(
            id,
            cleaned_text=payload.cleaned_text,
            raw_markdown=payload.raw_markdown,
            tiptap_json=payload.tiptap_json,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Document not found")
        return updated
    except AlfredException:
        raise
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        raise HTTPException(status_code=500, detail="Failed to update document") from exc


@router.get("/explorer", response_model=ExplorerDocumentsResponse)
def list_explorer_documents(
    limit: int = Query(24, ge=1, le=200),
    cursor: str | None = Query(None, description="Opaque cursor for pagination"),
    filter_topic: str | None = Query(None, description="Filter by primary topic"),
    search: str | None = Query(None, description="Optional search query"),
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> dict:
    try:
        return svc.list_explorer_documents(
            limit=limit,
            cursor=cursor,
            filter_topic=filter_topic,
            search=search,
        )
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        raise HTTPException(status_code=500, detail="Failed to list documents") from exc


@router.get("/semantic-map", response_model=SemanticMapResponse)
def get_semantic_map(
    limit: int = Query(5000, ge=1, le=20_000),
    refresh: bool = Query(False, description="Force recompute (bypass cache)"),
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> dict:
    try:
        points = svc.get_semantic_map_points(limit=limit, force_refresh=refresh)
        return {"points": points}
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        raise HTTPException(status_code=500, detail="Failed to build semantic map") from exc


@router.get("/search")
def search_documents(
    q: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> dict:
    try:
        data = svc.list_documents(q=q, topic=topic, limit=limit)
        return {"items": data["items"]}
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        raise HTTPException(status_code=500, detail="Failed to search documents") from exc
