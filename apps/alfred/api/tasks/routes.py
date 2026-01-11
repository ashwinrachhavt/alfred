from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from alfred.core.celery_client import get_celery_client

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    ready: bool
    successful: bool
    failed: bool
    result: Any | None = None
    error: str | None = None


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str, *, include_result: bool = True) -> TaskStatusResponse:
    celery_client = get_celery_client()
    async_result = celery_client.AsyncResult(task_id)

    result: Any | None = None
    error: str | None = None
    try:
        is_ready = async_result.ready()
        is_successful = async_result.successful()
        is_failed = async_result.failed()
        status = async_result.status

        if is_ready and include_result:
            if is_successful:
                try:
                    result = jsonable_encoder(async_result.result)
                except TypeError:
                    result = str(async_result.result)
            elif is_failed:
                error = str(async_result.result)
    except Exception as exc:  # pragma: no cover - depends on external broker/result backend
        # If Redis (or another result backend) is unavailable, avoid returning 500s for
        # status polling. Let the UI degrade gracefully.
        return TaskStatusResponse(
            task_id=task_id,
            status="unavailable",
            ready=False,
            successful=False,
            failed=False,
            result=None,
            error=str(exc),
        )

    return TaskStatusResponse(
        task_id=task_id,
        status=status,
        ready=is_ready,
        successful=is_successful,
        failed=is_failed,
        result=result,
        error=error,
    )
