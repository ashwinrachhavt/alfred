from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from alfred.core.celery_client import get_celery_client
from alfred.core.dependencies import get_doc_storage_service
from alfred.schemas.documents import (
    DocumentIngest,
    NoteCreate,
    NoteCreateRequest,
    NoteResponse,
    NotesListResponse,
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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
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
        res = svc.ingest_document_basic(ingest)
        if res.get("duplicate"):
            return PageResponse(id=res["id"], status="duplicate")
        return PageResponse(id=res["id"], status="stored")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
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
    except Exception as exc:  # pragma: no cover - external IO
        raise HTTPException(status_code=500, detail="Failed to fetch document") from exc


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
    except Exception as exc:  # pragma: no cover - external IO
        raise HTTPException(status_code=500, detail="Failed to search documents") from exc
