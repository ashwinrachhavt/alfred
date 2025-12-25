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
            "alfred.tasks.company_research",
            "alfred.tasks.company_insights",
            "alfred.tasks.company_interviews",
            "alfred.tasks.document_enrichment",
            "alfred.tasks.gmail_interviews",
            "alfred.tasks.interview_prep",
            "alfred.tasks.interviews_unified",
            "alfred.tasks.paraform_company_report",
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
            "alfred.tasks.company_insights.*": {"queue": "default"},
            "alfred.tasks.company_interviews.*": {"queue": "default"},
            "alfred.tasks.document_enrichment.*": {"queue": "default"},
            "alfred.tasks.gmail_interviews.*": {"queue": "default"},
            "alfred.tasks.interview_prep.*": {"queue": "default"},
            "alfred.tasks.interviews_unified.*": {"queue": "agent"},
            "alfred.tasks.paraform_company_report.*": {"queue": "default"},
        },
    )

    beat_schedule: dict[str, object] = {}
    if settings.enable_interview_reminders:
        beat_schedule |= {
            # Run hourly to catch 3d/1d/1h reminders without needing precise timing.
            "interview-reminders-hourly": {
                "task": "alfred.tasks.interview_prep.send_reminders",
                "schedule": crontab(minute=0),
                "kwargs": {"horizon_days": 14},
                "options": {"queue": "default"},
            }
        }

    if settings.enable_gmail and settings.enable_gmail_interview_poll:
        beat_schedule |= {
            "gmail-interview-poll-every-15m": {
                "task": "alfred.tasks.gmail.poll_interviews",
                "schedule": crontab(minute="*/15"),
                "kwargs": {"days_back": 7, "max_results": 25},
                "options": {"queue": "default"},
            }
        }

    if beat_schedule:
        celery_app.conf.beat_schedule = beat_schedule

    if include_tasks:
        celery_app.autodiscover_tasks(["alfred"])
        # Be explicit to avoid "Received unregistered task" when running workers from
        # different entrypoints/working directories.
        import alfred.tasks.company_insights  # noqa: F401
        import alfred.tasks.company_interviews  # noqa: F401
        import alfred.tasks.company_research  # noqa: F401
        import alfred.tasks.document_enrichment  # noqa: F401
        import alfred.tasks.gmail_interviews  # noqa: F401
        import alfred.tasks.interview_prep  # noqa: F401
        import alfred.tasks.interviews_unified  # noqa: F401
        import alfred.tasks.mind_palace_agent  # noqa: F401
        import alfred.tasks.paraform_company_report  # noqa: F401

    return celery_app
