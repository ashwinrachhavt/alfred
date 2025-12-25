from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from alfred.core.celery_client import get_celery_client
from alfred.core.dependencies import get_unified_interview_agent
from alfred.schemas.unified_interview import UnifiedInterviewRequest, UnifiedInterviewResponse
from alfred.services.interview_service import UnifiedInterviewAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interviews-unified", tags=["interviews-unified"])


class EnqueueUnifiedInterviewTaskResponse(BaseModel):
    task_id: str
    status_url: str
    status: str = "queued"


@router.post(
    "/process", response_model=UnifiedInterviewResponse | EnqueueUnifiedInterviewTaskResponse
)
async def unified_interview_process(
    payload: UnifiedInterviewRequest,
    response: Response,
    background: bool = Query(False, description="Enqueue a background task instead of blocking"),
    agent: UnifiedInterviewAgent = Depends(get_unified_interview_agent),
) -> UnifiedInterviewResponse | EnqueueUnifiedInterviewTaskResponse:
    """Unified endpoint for question collection, deep research, and practice sessions."""

    if background:
        celery_client = get_celery_client()
        async_result = celery_client.send_task(
            "alfred.tasks.interviews_unified.process",
            kwargs={"payload": payload.model_dump(mode="json")},
            queue="agent",
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return EnqueueUnifiedInterviewTaskResponse(
            task_id=async_result.id,
            status_url=f"/tasks/{async_result.id}",
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
