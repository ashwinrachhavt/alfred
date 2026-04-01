from __future__ import annotations

import logging

from celery.result import AsyncResult
from fastapi import APIRouter
from pydantic import BaseModel

from alfred.core.celery import create_celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

_celery = create_celery_app(include_tasks=False)


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # pending | running | completed | failed
    result: object | None = None
    error: str | None = None
    pipeline_step: str | None = None


_STATE_MAP = {
    "PENDING": "pending",
    "STARTED": "running",
    "RETRY": "running",
    "PROGRESS": "running",
    "SUCCESS": "completed",
    "FAILURE": "failed",
    "REVOKED": "failed",
}


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    """Poll the status of an async Celery task."""
    res = AsyncResult(task_id, app=_celery)
    mapped_status = _STATE_MAP.get(res.state, "pending")

    result = None
    error = None
    pipeline_step = None

    if mapped_status == "completed":
        result = res.result
    elif mapped_status == "failed":
        error = str(res.result) if res.result else "Task failed"

    # Extract pipeline_step from PROGRESS state metadata
    if res.state == "PROGRESS" and isinstance(res.info, dict):
        pipeline_step = res.info.get("pipeline_step")
    elif mapped_status == "running" and isinstance(res.info, dict):
        pipeline_step = res.info.get("pipeline_step")

    return TaskStatusResponse(
        task_id=task_id,
        status=mapped_status,
        result=result,
        error=error,
        pipeline_step=pipeline_step,
    )
