from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from alfred.core.celery_client import get_celery_client
from alfred.core.dependencies import get_knowledge_agent_service
from alfred.core.exceptions import ServiceUnavailableError
from alfred.schemas import AgentQueryRequest, AgentResponse
from alfred.services.agents.mind_palace_agent import KnowledgeAgentService

router = APIRouter(prefix="/api/mind-palace/agent", tags=["mind-palace"])
logger = logging.getLogger(__name__)


# Back-compat: tests override this dependency.
def get_agent_service() -> KnowledgeAgentService:
    return get_knowledge_agent_service()


class EnqueueMindPalaceTaskResponse(BaseModel):
    task_id: str
    status_url: str


@router.post(
    "/query",
    response_model=AgentResponse | EnqueueMindPalaceTaskResponse,
    status_code=status.HTTP_200_OK,
)
async def query_agent(
    payload: AgentQueryRequest,
    response: Response,
    background: bool = False,
    svc: KnowledgeAgentService = Depends(get_agent_service),
) -> AgentResponse | EnqueueMindPalaceTaskResponse:
    if background:
        celery_client = get_celery_client()
        async_result = celery_client.send_task(
            "alfred.tasks.mind_palace_agent.query",
            kwargs={
                "question": payload.question,
                "history": [m.model_dump() for m in payload.history],
                "context": payload.context,
            },
            queue="agent",
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return EnqueueMindPalaceTaskResponse(
            task_id=async_result.id,
            status_url=f"/tasks/{async_result.id}",
        )

    try:
        return await svc.ask(
            question=payload.question, history=payload.history, context=payload.context
        )
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Mind palace agent failed")
        raise ServiceUnavailableError("Mind palace agent failed") from exc
