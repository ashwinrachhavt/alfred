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
    if async_result.ready() and include_result:
        if async_result.successful():
            try:
                result = jsonable_encoder(async_result.result)
            except TypeError:
                result = str(async_result.result)
        elif async_result.failed():
            error = str(async_result.result)

    return TaskStatusResponse(
        task_id=task_id,
        status=async_result.status,
        ready=async_result.ready(),
        successful=async_result.successful(),
        failed=async_result.failed(),
        result=result,
        error=error,
    )
