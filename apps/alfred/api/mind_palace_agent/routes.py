from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from alfred.schemas import AgentQueryRequest, AgentResponse
from alfred.services.agents.mind_palace_agent import KnowledgeAgentService


router = APIRouter(prefix="/api/mind-palace/agent", tags=["mind-palace"])


def get_agent_service() -> KnowledgeAgentService:
    return KnowledgeAgentService()


@router.post("/query", response_model=AgentResponse, status_code=status.HTTP_200_OK)
async def query_agent(
    payload: AgentQueryRequest, svc: KnowledgeAgentService = Depends(get_agent_service)
) -> AgentResponse:
    try:
        return await svc.ask(question=payload.question, history=payload.history, context=payload.context)
    except Exception as exc:  # pragma: no cover - external IO
        raise HTTPException(status_code=500, detail=str(exc)) from exc

