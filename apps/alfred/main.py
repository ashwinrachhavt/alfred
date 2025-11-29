import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Dotenv is loaded by `apps/sitecustomize.py` when `apps/` is on sys.path.
from alfred.api import register_routes
from alfred.core.config import settings
from alfred.core.logging import setup_logging

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

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
