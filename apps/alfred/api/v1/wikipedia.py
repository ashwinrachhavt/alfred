from __future__ import annotations

from fastapi import APIRouter, Query

from alfred.services.wikipedia import retrieve_wikipedia

router = APIRouter(prefix="/api/v1/wikipedia", tags=["wikipedia"])


@router.get("/search")
def search(
    q: str = Query(...),
    lang: str = Query("en"),
    top_k_results: int = Query(3, ge=1, le=50),
    doc_content_chars_max: int = Query(4000, ge=200, le=20000),
    load_all_available_meta: bool = Query(False),
    load_max_docs: int = Query(100, ge=1, le=500),
):
    return retrieve_wikipedia(
        query=q,
        lang=lang,
        top_k_results=top_k_results,
        doc_content_chars_max=doc_content_chars_max,
        load_all_available_meta=load_all_available_meta,
        load_max_docs=load_max_docs,
    )
