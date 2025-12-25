from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import shared_task

from alfred.core.dependencies import get_unified_interview_agent
from alfred.schemas.unified_interview import UnifiedInterviewRequest, UnifiedInterviewResponse

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.interviews_unified.process")
def unified_interview_process_task(*, payload: dict[str, Any]) -> dict[str, Any]:
    """Run the unified interview workflow in a background worker.

    Notes:
    - Celery tasks are synchronous; we run the async agent via `asyncio.run`.
    - The `payload` must be JSON-serializable (use `model_dump(mode="json")`).
    """

    request = UnifiedInterviewRequest.model_validate(payload)
    agent = get_unified_interview_agent()

    async def _run() -> UnifiedInterviewResponse:
        return await agent.process(request)

    result = asyncio.run(_run())
    return result.model_dump(mode="json")
