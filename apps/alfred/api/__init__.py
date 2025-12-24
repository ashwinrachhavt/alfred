"""API router registration helpers.

To avoid import-time side effects (e.g., initializing LLM clients) during test
collection or when importing submodules, routers are imported lazily inside
`register_routes` rather than at module import time.
"""

from fastapi import FastAPI


def register_routes(app: FastAPI) -> None:
    """Attach all API routers (lazy imports)."""
    # Import routers only when registering to avoid heavy side effects during import.
    from alfred.api.brand import router as brand_router
    from alfred.api.calendar import router as calendar_router
    from alfred.api.company import router as company_router
    from alfred.api.documents import router as documents_router
    from alfred.api.gmail import router as gmail_router
    from alfred.api.interviews_unified import router as interviews_unified_router
    from alfred.api.learning import router as learning_router
    from alfred.api.linear import router as linear_router
    from alfred.api.mind_palace_agent import router as mind_palace_agent_router
    from alfred.api.notion import router as notion_router
    from alfred.api.portfolio import router as portfolio_router
    from alfred.api.rag import router as rag_router
    from alfred.api.system import router as system_router
    from alfred.api.tasks import router as tasks_router
    from alfred.api.tools import router as tools_router
    from alfred.api.web import router as web_router
    from alfred.api.wikipedia import router as wikipedia_router
    from alfred.api.zettels import router as zettels_router

    routers = [
        system_router,
        portfolio_router,
        tasks_router,
        rag_router,
        notion_router,
        gmail_router,
        interviews_unified_router,
        linear_router,
        calendar_router,
        company_router,
        web_router,
        documents_router,
        mind_palace_agent_router,
        wikipedia_router,
        tools_router,
        brand_router,
        learning_router,
        zettels_router,
    ]
    for router in routers:
        app.include_router(router)
