from __future__ import annotations

from celery import Celery
from kombu import Queue

from alfred.core.settings import settings


def create_celery_app(*, include_tasks: bool = True) -> Celery:
    """Create a configured Celery app.

    `include_tasks=False` creates a lightweight client suitable for the API
    process (enqueue/poll only) without importing task modules.
    """

    celery_app = Celery(
        "alfred",
        broker=settings.redis_url,
        backend=settings.redis_url,
    )
    celery_app.conf.update(
        accept_content=["json"],
        enable_utc=True,
        result_serializer="json",
        task_serializer="json",
        timezone="UTC",
        task_track_started=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_default_queue="default",
        task_queues=(
            Queue("default"),
            Queue("agent"),
        ),
        task_routes={
            "alfred.tasks.mind_palace_agent.*": {"queue": "agent"},
        },
    )

    if include_tasks:
        celery_app.autodiscover_tasks(["alfred"])

    return celery_app
