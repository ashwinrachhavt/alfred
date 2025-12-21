from __future__ import annotations

from celery import Celery
from kombu import Queue

from alfred.core.settings import settings


def create_celery_app(*, include_tasks: bool = True) -> Celery:
    """Create a configured Celery app.

    `include_tasks=False` creates a lightweight client suitable for the API
    process (enqueue/poll only) without importing task modules.
    """

    task_modules = (
        [
            "alfred.tasks.mind_palace_agent",
            "alfred.tasks.company_research",
            "alfred.tasks.document_enrichment",
        ]
        if include_tasks
        else []
    )

    celery_app = Celery(
        "alfred",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=task_modules,
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
            "alfred.tasks.company_research.*": {"queue": "default"},
            "alfred.tasks.document_enrichment.*": {"queue": "default"},
        },
    )

    if include_tasks:
        celery_app.autodiscover_tasks(["alfred"])
        # Be explicit to avoid "Received unregistered task" when running workers from
        # different entrypoints/working directories.
        import alfred.tasks.company_research  # noqa: F401
        import alfred.tasks.document_enrichment  # noqa: F401
        import alfred.tasks.mind_palace_agent  # noqa: F401

    return celery_app
