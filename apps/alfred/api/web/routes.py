from fastapi import APIRouter, Query

from alfred.core.tracing import lf_update_span, observe
from alfred.services.web_search import search_web

router = APIRouter(prefix="/api/web", tags=["web"])


@router.get("/search")
@observe(name="api_web_search", as_type="chain")
def search(
    q: str = Query(...),
    mode: str | None = Query(
        None, pattern=r"^(auto|multi|brave|ddg|exa|tavily|you|searx|langsearch)$"
    ),
    provider: str | None = Query(
        None, pattern=r"^(auto|brave|ddg|exa|tavily|you|searx|langsearch)$"
    ),
    brave_pages: int = Query(10, ge=1, le=10),
    ddg_max_results: int = Query(50, ge=1, le=200),
    exa_num_results: int = Query(100, ge=1, le=100),
    tavily_max_results: int = Query(20, ge=1, le=50),
    tavily_topic: str = Query("general"),
    you_num_results: int = Query(19, ge=1, le=19),
    searx_k: int = Query(10, ge=1, le=100),
):
    effective_mode = mode or provider or "auto"
    result = search_web(
        q=q,
        mode=effective_mode,
        brave_pages=brave_pages,
        ddg_max_results=ddg_max_results,
        exa_num_results=exa_num_results,
        tavily_max_results=tavily_max_results,
        tavily_topic=tavily_topic,
        you_num_results=you_num_results,
        searx_k=searx_k,
    )
    try:
        lf_update_span(
            input={
                "q": q,
                "mode": effective_mode,
                "searx_k": searx_k,
            },
            output={"hits_count": len(result.get("hits", []))},
            metadata={"endpoint": "/api/web/search"},
        )
    except Exception:
        pass
    return result
