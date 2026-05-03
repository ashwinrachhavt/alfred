from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from alfred.api.dependencies import get_db_session
from alfred.schemas.chat import ChatOmniboxResponse
from alfred.services.chat_omnibox import ChatOmniboxService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/omnibox", response_model=ChatOmniboxResponse)
def search_omnibox(
    q: str | None = Query(default=None),
    limit: int = Query(default=8, ge=1, le=25),
    session: Session = Depends(get_db_session),
) -> ChatOmniboxResponse:
    service = ChatOmniboxService(session=session)
    return ChatOmniboxResponse(results=service.search(query=q, limit=limit))
