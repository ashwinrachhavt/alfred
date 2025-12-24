from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from alfred.core.dependencies import get_unified_interview_agent
from alfred.schemas.unified_interview import UnifiedInterviewRequest, UnifiedInterviewResponse
from alfred.services.unified_interview_agent import UnifiedInterviewAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interviews-unified", tags=["interviews-unified"])


@router.post("/process", response_model=UnifiedInterviewResponse)
async def unified_interview_process(
    payload: UnifiedInterviewRequest,
    agent: UnifiedInterviewAgent = Depends(get_unified_interview_agent),
) -> UnifiedInterviewResponse:
    """Unified endpoint for question collection, deep research, and practice sessions."""

    try:
        return await agent.process(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - unexpected runtime failures
        logger.exception("Unified interview processing failed")
        raise HTTPException(
            status_code=500, detail=f"Unified interview agent failed: {exc}"
        ) from exc
