import logging
import os
import sys
from datetime import timedelta

from celery import Celery

from alfred.core.config import settings
from alfred.core.logging import setup_logging

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

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

# Beat schedule: renew Gmail watch daily if enabled/configured
app.conf.beat_schedule = {
    "renew-gmail-watch-daily": {
        # Adjusted task path to the new package name; ensure module exists if enabled
        "task": "alfred.tasks.gmail_watch.renew_gmail_watch",
        "schedule": timedelta(days=1),
        "options": {"expires": 60 * 60},
    }
}

logging.getLogger(__name__).info("Celery app initialized")
