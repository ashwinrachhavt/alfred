import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Environment is loaded by Pydantic Settings (see alfred.core.config).
from alfred.api import register_routes
from alfred.core.config import settings
from alfred.core.logging import setup_logging
from alfred.services.mind_palace.doc_storage import DocStorageService

# Bytecode disabling is controlled via environment (Makefile/Docker) or settings.

# Initialize logging early so all modules inherit the handlers/level
setup_logging()

app = FastAPI(title="Alfred API")
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
        DocStorageService().ensure_indexes()
        logging.getLogger(__name__).info("DocStorage indexes ensured")
    except Exception as exc:  # pragma: no cover - external dependency
        logging.getLogger(__name__).warning("Failed to ensure DocStorage indexes: %s", exc)
