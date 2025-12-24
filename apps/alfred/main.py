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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routes(app)
mount_admin(app)

logger = logging.getLogger(__name__)
logger.info("Alfred API initialized")
