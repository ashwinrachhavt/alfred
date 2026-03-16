from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
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
            "alfred.tasks.deep_research",
            "alfred.tasks.document_enrichment",
            "alfred.tasks.document_processing",
            "alfred.tasks.document_title_image",
            "alfred.tasks.learning_concepts",
            "alfred.tasks.document_concepts",
            "alfred.tasks.notion_import",
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
            "alfred.tasks.deep_research.*": {"queue": "default"},
            "alfred.tasks.document_enrichment.*": {"queue": "default"},
            "alfred.tasks.document_processing.*": {"queue": "default"},
            "alfred.tasks.document_title_image.*": {"queue": "default"},
            "alfred.tasks.learning_concepts.*": {"queue": "default"},
            "alfred.tasks.document_concepts.*": {"queue": "default"},
            "alfred.tasks.notion_import.*": {"queue": "default"},
        },
    )

    beat_schedule: dict[str, object] = {}

    if settings.enable_learning_concept_extraction_nightly:
        beat_schedule |= {
            "learning-concepts-nightly": {
                "task": "alfred.tasks.learning_concepts.batch_extract",
                "schedule": crontab(
                    minute=int(settings.learning_concept_extraction_nightly_minute),
                    hour=int(settings.learning_concept_extraction_nightly_hour),
                ),
                "kwargs": {
                    "limit": int(settings.learning_concept_extraction_batch_limit),
                    "min_age_hours": int(settings.learning_concept_extraction_min_age_hours),
                    "enqueue_only": True,
                    "force": False,
                },
                "options": {"queue": "default"},
            }
        }

    if settings.enable_document_concept_extraction_nightly:
        beat_schedule |= {
            "document-concepts-nightly": {
                "task": "alfred.tasks.document_concepts.batch_extract",
                "schedule": crontab(
                    minute=int(settings.document_concept_extraction_nightly_minute),
                    hour=int(settings.document_concept_extraction_nightly_hour),
                ),
                "kwargs": {
                    "limit": int(settings.document_concept_extraction_batch_limit),
                    "min_age_hours": int(settings.document_concept_extraction_min_age_hours),
                    "enqueue_only": True,
                    "force": False,
                },
                "options": {"queue": "default"},
            }
        }

    if beat_schedule:
        celery_app.conf.beat_schedule = beat_schedule

    if include_tasks:
        celery_app.autodiscover_tasks(["alfred"])
        # Be explicit to avoid "Received unregistered task" when running workers from
        # different entrypoints/working directories.
        import alfred.tasks.deep_research
        import alfred.tasks.document_concepts
        import alfred.tasks.document_enrichment
        import alfred.tasks.document_processing
        import alfred.tasks.document_title_image
        import alfred.tasks.learning_concepts
        import alfred.tasks.mind_palace_agent
        import alfred.tasks.notion_import  # noqa: F401

    return celery_app
