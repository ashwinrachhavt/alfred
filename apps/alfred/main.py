import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Environment is loaded by Pydantic Settings (see alfred.core.settings).
from alfred.api import register_routes
from alfred.core.dependencies import (
    get_company_insights_service,
    get_company_interviews_service,
    get_doc_storage_service,
    get_interview_prep_service,
    get_panel_interview_service,
)
from alfred.core.exceptions import register_exception_handlers
from alfred.core.logging import setup_logging
from alfred.core.settings import settings

# Bytecode disabling is controlled via environment (Makefile/Docker) or settings.

# Initialize logging early so all modules inherit the handlers/level
setup_logging()

app = FastAPI(title="Alfred API")
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routes(app)

logger = logging.getLogger(__name__)
logger.info("Alfred API initialized")


@app.on_event("startup")
def _ensure_indexes_on_startup() -> None:
    """Ensure Mongo indexes for document storage are created once at boot.

    Best-effort: logs a warning on failure but does not block app startup.
    """
    try:
        get_doc_storage_service().ensure_indexes()
        logging.getLogger(__name__).info("DocStorage indexes ensured")
    except Exception as exc:  # pragma: no cover - external dependency
        logging.getLogger(__name__).warning("Failed to ensure DocStorage indexes: %s", exc)

    try:
        get_interview_prep_service().ensure_indexes()
        logging.getLogger(__name__).info("InterviewPrep indexes ensured")
    except Exception as exc:  # pragma: no cover - external dependency
        logging.getLogger(__name__).warning("Failed to ensure InterviewPrep indexes: %s", exc)

    try:
        get_company_insights_service().ensure_indexes()
        logging.getLogger(__name__).info("CompanyInsights indexes ensured")
    except Exception as exc:  # pragma: no cover - external dependency
        logging.getLogger(__name__).warning("Failed to ensure CompanyInsights indexes: %s", exc)

    try:
        get_company_interviews_service().ensure_indexes()
        logging.getLogger(__name__).info("CompanyInterviews indexes ensured")
    except Exception as exc:  # pragma: no cover - external dependency
        logging.getLogger(__name__).warning("Failed to ensure CompanyInterviews indexes: %s", exc)

    try:
        get_panel_interview_service().ensure_indexes()
        logging.getLogger(__name__).info("PanelInterview indexes ensured")
    except Exception as exc:  # pragma: no cover - external dependency
        logging.getLogger(__name__).warning("Failed to ensure PanelInterview indexes: %s", exc)
