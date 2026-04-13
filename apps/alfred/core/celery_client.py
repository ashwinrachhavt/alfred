from __future__ import annotations

import errno
from functools import lru_cache
from typing import Any

from celery import Celery
from kombu.exceptions import OperationalError

from alfred.core.celery import create_celery_app

_BROKER_ERRNOS = {
    errno.ECONNREFUSED,
    errno.ETIMEDOUT,
    errno.EHOSTUNREACH,
    errno.ENETUNREACH,
}


class BrokerUnavailableError(RuntimeError):
    """Raised when the Celery broker cannot be reached."""


@lru_cache
def get_celery_client() -> Celery:
    """Return a lightweight Celery client for the API process.

    This client is used to enqueue tasks and poll their status/result without
    importing task modules (which may pull in heavy AI dependencies).
    """

    return create_celery_app(include_tasks=False)


def _iter_exception_chain(exc: BaseException):
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        yield current
        seen.add(id(current))
        if current.__cause__ is not None:
            current = current.__cause__
            continue
        current = current.__context__


def _is_broker_unavailable(exc: BaseException) -> bool:
    for candidate in _iter_exception_chain(exc):
        if isinstance(candidate, OperationalError):
            return True
        if isinstance(candidate, ConnectionRefusedError | TimeoutError):
            return True
        if isinstance(candidate, OSError) and candidate.errno in _BROKER_ERRNOS:
            return True

    return False


def dispatch_task(
    task_name: str,
    *,
    kwargs: dict[str, Any] | None = None,
    **options: Any,
) -> Any:
    """Dispatch a Celery task and normalize broker connectivity failures."""

    try:
        return get_celery_client().send_task(task_name, kwargs=kwargs or {}, **options)
    except Exception as exc:
        if _is_broker_unavailable(exc):
            raise BrokerUnavailableError("Background worker unavailable") from exc
        raise
