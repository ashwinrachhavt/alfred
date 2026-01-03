import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alfred.admin import mount_admin

# Environment is loaded by Pydantic Settings (see alfred.core.settings).
from alfred.api import register_routes
from alfred.core.exceptions import register_exception_handlers
from alfred.core.logging import setup_logging
from alfred.core.settings import settings

# Bytecode disabling is controlled via environment (Makefile/Docker) or settings.

# Initialize logging early so all modules inherit the handlers/level
setup_logging()

app = FastAPI(title="Alfred API")
register_exception_handlers(app)

cors_origins = settings.cors_allow_origins
cors_allow_credentials = "*" not in cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routes(app)
mount_admin(app)


@app.on_event("shutdown")
def _shutdown() -> None:
    """Best-effort cleanup for long-lived external clients."""

    try:
        from alfred.core.dependencies import get_graph_service

        graph = get_graph_service()
        if graph is not None:
            graph.close()
    except Exception:
        pass

    try:
        from alfred.core.redis_client import get_redis_client

        redis_client = get_redis_client()
        close = getattr(redis_client, "close", None) if redis_client is not None else None
        if callable(close):
            close()
    except Exception:
        pass


logger = logging.getLogger(__name__)
logger.info("Alfred API initialized")
