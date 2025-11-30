"""API router registration helpers.

To avoid import-time side effects (e.g., initializing LLM clients) during test
collection or when importing submodules, routers are imported lazily inside
`register_routes` rather than at module import time.
"""

from fastapi import FastAPI


def register_routes(app: FastAPI) -> None:
    """Attach all API routers (lazy imports)."""
    # Import routers only when registering to avoid heavy side effects during import.
    from alfred.api.calendar import router as calendar_router
    from alfred.api.company import router as company_router
    from alfred.api.documents import router as documents_router
    from alfred.api.gmail import router as gmail_router
    from alfred.api.mind_palace_agent import router as mind_palace_agent_router
    from alfred.api.notion import router as notion_router
    from alfred.api.rag import router as rag_router
    from alfred.api.system import router as system_router
    from alfred.api.web import router as web_router
    from alfred.api.wikipedia import router as wikipedia_router

    routers = [
        system_router,
        rag_router,
        notion_router,
        gmail_router,
        calendar_router,
        company_router,
        web_router,
        documents_router,
        mind_palace_agent_router,
        wikipedia_router,
    ]
    for router in routers:
        app.include_router(router)
