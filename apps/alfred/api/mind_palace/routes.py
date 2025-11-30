from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from alfred.services.mind_palace import PageInput, PageResult
from alfred.services.mind_palace.enrichment import EnrichmentService
from alfred.services.mind_palace.extraction import ExtractionService
from alfred.services.mind_palace.service import MindPalaceService

router = APIRouter(prefix="/api/mind-palace", tags=["mind-palace"])


def get_service() -> MindPalaceService:
    svc = MindPalaceService(extractor=ExtractionService(), enricher=EnrichmentService())
    try:
        svc.ensure_indexes()
    except Exception:
        pass
    return svc


class PageRequest(BaseModel):
    raw_text: str = Field(..., min_length=50)
    html: Optional[str] = None
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    selection_type: Literal["full_page", "selection", "article_only"] = "full_page"


class PageResponse(BaseModel):
    id: str
    status: str


@router.post("/page/extract", response_model=PageResponse)
async def create_page(
    payload: PageRequest,
    svc: MindPalaceService = Depends(get_service),
) -> PageResponse:
    try:
        res: PageResult = svc.create_page(
            PageInput(
                raw_text=payload.raw_text,
                html=payload.html,
                page_url=payload.page_url,
                page_title=payload.page_title,
                selection_type=payload.selection_type,
            ),
            enrich=True,
        )
        return PageResponse(id=res.id, status=res.status)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/doc/{id}")
async def get_document(id: str, svc: MindPalaceService = Depends(get_service)) -> dict[str, Any]:
    doc = svc.get(id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/search")
async def search_documents(
    q: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    svc: MindPalaceService = Depends(get_service),
) -> dict[str, Any]:
    docs = svc.search(q=q, topic=topic, domain=domain, limit=limit)
    return {"items": docs}
