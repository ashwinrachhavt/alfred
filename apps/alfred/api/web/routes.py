from fastapi import APIRouter, Query

from alfred.services.web_service import search_web

router = APIRouter(prefix="/api/web", tags=["web"])


@router.get("/search")
def search(
    q: str = Query(...),
    searx_k: int = Query(10, ge=1, le=100),
    categories: str | None = Query(None),
    time_range: str | None = Query(None),
):
    return search_web(q=q, searx_k=searx_k, categories=categories, time_range=time_range)
