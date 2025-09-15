from fastapi import APIRouter, Query

from alfred.services.web_search import search_web

router = APIRouter(prefix="/api/v1/web", tags=["web"])


@router.get("/search")
def search(
    q: str = Query(...),
    mode: str | None = Query(None, pattern=r"^(auto|multi|brave|ddg|exa|tavily|you)$"),
    provider: str | None = Query(None, pattern=r"^(auto|brave|ddg|exa|tavily|you)$"),
    brave_pages: int = Query(10, ge=1, le=10),
    ddg_max_results: int = Query(50, ge=1, le=200),
    exa_num_results: int = Query(100, ge=1, le=100),
    tavily_max_results: int = Query(20, ge=1, le=50),
    tavily_topic: str = Query("general"),
    you_num_results: int = Query(19, ge=1, le=19),
):
    effective_mode = mode or provider or "auto"
    return search_web(
        q=q,
        mode=effective_mode,
        brave_pages=brave_pages,
        ddg_max_results=ddg_max_results,
        exa_num_results=exa_num_results,
        tavily_max_results=tavily_max_results,
        tavily_topic=tavily_topic,
        you_num_results=you_num_results,
    )
