from datetime import timedelta

from alfred_app.core.config import settings
from celery import Celery

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
        "task": "alfred_app.tasks.gmail_watch.renew_gmail_watch",
        "schedule": timedelta(days=1),
        "options": {"expires": 60 * 60},
    }
}
