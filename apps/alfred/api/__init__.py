"""API router registration helpers."""

from fastapi import FastAPI

from alfred.api.calendar import router as calendar_router
from alfred.api.company import router as company_router
from alfred.api.copilotkit import register_copilotkit_endpoint
from alfred.api.crew import router as crew_router
from alfred.api.gmail import router as gmail_router
from alfred.api.google_connect import (
    api_router as google_api_router,
)
from alfred.api.google_connect import (
    legacy_router as google_legacy_router,
)
from alfred.api.google_connect import (
    ui_router as google_ui_router,
)
from alfred.api.notion import router as notion_router
from alfred.api.rag import router as rag_router
from alfred.api.system import router as system_router
from alfred.api.web import router as web_router
from alfred.api.wikipedia import router as wikipedia_router

ROUTERS = [
    system_router,
    rag_router,
    notion_router,
    gmail_router,
    calendar_router,
    company_router,
    google_api_router,
    web_router,
    wikipedia_router,
    crew_router,
]


def register_routes(app: FastAPI) -> None:
    """Attach all API routers."""
    for router in ROUTERS:
        app.include_router(router)
    app.include_router(google_ui_router)
    app.include_router(google_legacy_router)
    # Temporary compatibility for legacy clients still using /api/v1/notion/*
    app.include_router(notion_router, prefix="/api/v1")
    register_copilotkit_endpoint(app)
