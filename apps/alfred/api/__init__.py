"""API router registration helpers.

To avoid import-time side effects (e.g., initializing LLM clients) during test
collection or when importing submodules, routers are imported lazily inside
`register_routes` rather than at module import time.
"""

from fastapi import FastAPI


def register_routes(app: FastAPI) -> None:
    """Attach all API routers (lazy imports)."""

    # Import routers only when registering to avoid heavy side effects during import.
    from alfred.api.admin import router as admin_router

    # Knowledge import routers
    from alfred.api.arxiv_import import router as arxiv_import_router
    from alfred.api.calendar import router as calendar_router
    from alfred.api.documents import router as documents_router
    from alfred.api.gdrive import router as gdrive_router
    from alfred.api.github_import import router as github_import_router
    from alfred.api.gmail import router as gmail_router
    from alfred.api.google import router as google_router
    from alfred.api.google_tasks import router as google_tasks_router
    from alfred.api.hypothesis import router as hypothesis_router
    from alfred.api.intelligence import router as intelligence_router
    from alfred.api.learning import router as learning_router
    from alfred.api.linear import router as linear_router
    from alfred.api.mind_palace_agent import router as mind_palace_agent_router
    from alfred.api.notes import router as notes_router
    from alfred.api.notion import router as notion_router
    from alfred.api.pipeline import router as pipeline_router
    from alfred.api.pocket import router as pocket_router
    from alfred.api.rag import router as rag_router
    from alfred.api.reading import router as reading_router
    from alfred.api.readwise import router as readwise_router
    from alfred.api.research import router as research_router
    from alfred.api.rss import router as rss_router
    from alfred.api.semantic_scholar import router as semantic_scholar_router
    from alfred.api.slack_import import router as slack_import_router
    from alfred.api.system import router as system_router
    from alfred.api.system_design import router as system_design_router
    from alfred.api.tasks import router as tasks_router
    from alfred.api.todoist import router as todoist_router
    from alfred.api.tools import router as tools_router
    from alfred.api.web import router as web_router
    from alfred.api.whiteboards import router as whiteboards_router
    from alfred.api.wikipedia import router as wikipedia_router
    from alfred.api.writing import router as writing_router
    from alfred.api.zettels import router as zettels_router

    routers = [
        system_router,
        admin_router,
        tasks_router,
        intelligence_router,
        rag_router,
        notion_router,
        google_router,
        gmail_router,
        notes_router,
        linear_router,
        calendar_router,
        research_router,
        web_router,
        documents_router,
        mind_palace_agent_router,
        wikipedia_router,
        tools_router,
        learning_router,
        zettels_router,
        system_design_router,
        pipeline_router,
        whiteboards_router,
        writing_router,
        reading_router,
        # Knowledge import routers
        readwise_router,
        github_import_router,
        gdrive_router,
        slack_import_router,
        arxiv_import_router,
        todoist_router,
        google_tasks_router,
        pocket_router,
        hypothesis_router,
        semantic_scholar_router,
        rss_router,
    ]
    for router in routers:
        app.include_router(router)
