from __future__ import annotations

from functools import lru_cache

from celery import Celery

from alfred.core.celery import create_celery_app


@lru_cache
def get_celery_client() -> Celery:
    """Return a lightweight Celery client for the API process.

    This client is used to enqueue tasks and poll their status/result without
    importing task modules (which may pull in heavy AI dependencies).
    """

    return create_celery_app(include_tasks=False)
