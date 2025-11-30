from __future__ import annotations

from typing import Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from alfred.services.mind_palace.doc_storage import DocStorageService
from alfred.schemas.mind_palace import NoteCreate, DocumentIngest
from alfred.schemas.mind_palace import (
    NoteCreateRequest,
    NoteResponse,
    NotesListResponse,
)

router = APIRouter(prefix="/api/mind-palace", tags=["mind-palace"])


# ----------------------------
# Notes: Quick capture endpoints
# ----------------------------

def get_doc_storage_service() -> DocStorageService:
    # Indexes are ensured on app startup; this is a simple DI hook.
    return DocStorageService()


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


# ---------------------------------
# Back-compat: page, doc, search
# ---------------------------------


class PageRequest(BaseModel):
    raw_text: str = Field(..., min_length=50)
    html: str | None = None
    page_url: str | None = None
    page_title: str | None = None
    selection_type: Literal["full_page", "selection", "article_only"] = "full_page"


class PageResponse(BaseModel):
    id: str
    status: str


@router.post("/page/extract", response_model=PageResponse)
def create_page(
    payload: PageRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> PageResponse:
    # Minimal ingestion path using DocumentIngest; no enrichment.
    try:
        ingest = DocumentIngest(
            source_url=(payload.page_url or "about:blank"),
            title=payload.page_title,
            cleaned_text=payload.raw_text,
            content_type="web",
            raw_html=payload.html,
        )
        res = svc.ingest_document(ingest)
        status_txt = "ready"
        return PageResponse(id=res["id"], status=status_txt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover - external IO
        raise HTTPException(status_code=500, detail="Failed to ingest page") from exc


@router.get("/doc/{id}")
def get_document(
    id: str,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> dict:
    try:
        if not ObjectId.is_valid(id):
            raise HTTPException(status_code=400, detail="Invalid id")
        doc = svc.database.get_collection("documents").find_one({"_id": ObjectId(id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        # Serialize minimal fields similar to list_documents
        return {
            "id": str(doc.get("_id")),
            "title": doc.get("title"),
            "source_url": doc.get("source_url"),
            "canonical_url": doc.get("canonical_url"),
            "topics": doc.get("topics"),
            "captured_at": doc.get("captured_at"),
            "tokens": doc.get("tokens"),
            "summary": (
                (doc.get("summary") or {}).get("short") if isinstance(doc.get("summary"), dict) else None
            ),
        }
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
    # domain filter is not directly supported in DocStorageService.list_documents;
    # we approximate via q if provided, otherwise ignore domain.
    try:
        data = svc.list_documents(q=q, topic=topic, limit=limit)
        return {"items": data["items"]}
    except Exception as exc:  # pragma: no cover - external IO
        raise HTTPException(status_code=500, detail="Failed to search documents") from exc
