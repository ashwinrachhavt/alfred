import logging

from celery import Celery

from alfred.core.logging import setup_logging
from alfred.core.settings import settings

# Bytecode disabling is controlled via environment or settings.

setup_logging()

app = Celery(
    "alfred",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# No beat schedule defined by default to avoid referencing missing tasks.

logging.getLogger(__name__).info("Celery app initialized")
