from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import shared_task

from alfred.core.dependencies import get_knowledge_agent_service

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.mind_palace_agent.query")
def mind_palace_agent_query_task(
    *,
    question: str,
    history: list[dict[str, str]] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the Mind Palace agent query in a background worker."""

    logger.info("Running mind-palace agent task")
    svc = get_knowledge_agent_service()

    async def _run() -> Any:
        return await svc.ask(question=question, history=history or [], context=context or {})

    result = asyncio.run(_run())
    if hasattr(result, "model_dump"):
        return result.model_dump()  # type: ignore[no-any-return]
    if isinstance(result, dict):
        return result
    return {"answer": str(result), "sources": None, "meta": {"mode": "unknown"}}
