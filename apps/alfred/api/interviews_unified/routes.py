from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from alfred.agents.interviews_unified.agent import UnifiedInterviewAgent
from alfred.core.celery_client import get_celery_client
from alfred.core.dependencies import get_unified_interview_agent
from alfred.schemas.unified_interview import UnifiedInterviewRequest, UnifiedInterviewResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interviews-unified", tags=["interviews-unified"])


class EnqueueUnifiedInterviewTaskResponse(BaseModel):
    task_id: str
    status_url: str
    status: str = "queued"


def _enqueue_unified_interview_task(*, task_id: str, payload: dict) -> None:
    """Publish the unified interview task to Celery.

    This is executed via FastAPI BackgroundTasks so the HTTP request can return
    quickly even if the broker connection is slow or temporarily unavailable.
    """

    celery_client = get_celery_client()
    celery_client.send_task(
        "alfred.tasks.interviews_unified.process",
        task_id=task_id,
        kwargs={"payload": payload},
        queue="agent",
    )


@router.post(
    "/process", response_model=UnifiedInterviewResponse | EnqueueUnifiedInterviewTaskResponse
)
async def unified_interview_process(
    payload: UnifiedInterviewRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    background: bool = Query(False, description="Enqueue a background task instead of blocking"),
    agent: UnifiedInterviewAgent = Depends(get_unified_interview_agent),
) -> UnifiedInterviewResponse | EnqueueUnifiedInterviewTaskResponse:
    """Unified endpoint for question collection, deep research, and practice sessions."""

    if background:
        task_id = str(uuid.uuid4())
        background_tasks.add_task(
            _enqueue_unified_interview_task,
            task_id=task_id,
            payload=payload.model_dump(mode="json"),
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return EnqueueUnifiedInterviewTaskResponse(
            task_id=task_id,
            status_url=f"/tasks/{task_id}",
        )

    try:
        return await agent.process(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - unexpected runtime failures
        logger.exception("Unified interview processing failed")
        raise HTTPException(
            status_code=500, detail=f"Unified interview agent failed: {exc}"
        ) from exc
