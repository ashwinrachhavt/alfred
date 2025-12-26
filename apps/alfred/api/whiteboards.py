from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from alfred.api.dependencies import get_db_session
from alfred.schemas.whiteboard import (
    WhiteboardCommentCreate,
    WhiteboardCommentOut,
    WhiteboardCreate,
    WhiteboardOut,
    WhiteboardRevisionCreate,
    WhiteboardRevisionOut,
    WhiteboardUpdate,
    WhiteboardWithRevision,
)
from alfred.services.whiteboard_service import WhiteboardService

router = APIRouter(prefix="/api/whiteboards", tags=["whiteboards"])


def _to_whiteboard_response(board, revision):  # noqa: ANN001
    base = WhiteboardOut.model_validate(board).model_dump()
    return WhiteboardWithRevision(
        **base,
        latest_revision=WhiteboardRevisionOut.model_validate(revision) if revision else None,
    )


@router.post("", response_model=WhiteboardWithRevision, status_code=status.HTTP_201_CREATED)
def create_whiteboard(
    payload: WhiteboardCreate,
    session: Session = Depends(get_db_session),
) -> WhiteboardWithRevision:
    service = WhiteboardService(session)
    board, revision = service.create_whiteboard(**payload.model_dump())
    return _to_whiteboard_response(board, revision)


@router.get("", response_model=list[WhiteboardWithRevision])
def list_whiteboards(
    include_archived: bool = False,
    limit: int = 50,
    skip: int = 0,
    session: Session = Depends(get_db_session),
) -> list[WhiteboardWithRevision]:
    service = WhiteboardService(session)
    boards = service.list_whiteboards(include_archived=include_archived, limit=limit, skip=skip)
    return [
        _to_whiteboard_response(board, service.latest_revision(whiteboard_id=board.id or 0))
        for board in boards
    ]


@router.get("/{board_id}", response_model=WhiteboardWithRevision)
def get_whiteboard(board_id: int, session: Session = Depends(get_db_session)) -> WhiteboardWithRevision:
    service = WhiteboardService(session)
    board = service.get_whiteboard(board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Whiteboard not found")
    revision = service.latest_revision(whiteboard_id=board.id or 0)
    return _to_whiteboard_response(board, revision)


@router.patch("/{board_id}", response_model=WhiteboardWithRevision)
def update_whiteboard(
    board_id: int,
    payload: WhiteboardUpdate,
    session: Session = Depends(get_db_session),
) -> WhiteboardWithRevision:
    service = WhiteboardService(session)
    board = service.get_whiteboard(board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Whiteboard not found")
    updated = service.update_whiteboard(board, **payload.model_dump(exclude_unset=True))
    revision = service.latest_revision(whiteboard_id=board.id or 0)
    return _to_whiteboard_response(updated, revision)


@router.post(
    "/{board_id}/revisions",
    response_model=WhiteboardRevisionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_revision(
    board_id: int,
    payload: WhiteboardRevisionCreate,
    session: Session = Depends(get_db_session),
) -> WhiteboardRevisionOut:
    service = WhiteboardService(session)
    if not service.get_whiteboard(board_id):
        raise HTTPException(status_code=404, detail="Whiteboard not found")
    revision = service.create_revision(whiteboard_id=board_id, **payload.model_dump())
    return WhiteboardRevisionOut.model_validate(revision)


@router.get("/{board_id}/revisions", response_model=list[WhiteboardRevisionOut])
def list_revisions(board_id: int, session: Session = Depends(get_db_session)) -> list[WhiteboardRevisionOut]:
    service = WhiteboardService(session)
    if not service.get_whiteboard(board_id):
        raise HTTPException(status_code=404, detail="Whiteboard not found")
    revisions = service.list_revisions(whiteboard_id=board_id)
    return [WhiteboardRevisionOut.model_validate(item) for item in revisions]


@router.post(
    "/{board_id}/comments",
    response_model=WhiteboardCommentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    board_id: int,
    payload: WhiteboardCommentCreate,
    session: Session = Depends(get_db_session),
) -> WhiteboardCommentOut:
    service = WhiteboardService(session)
    if not service.get_whiteboard(board_id):
        raise HTTPException(status_code=404, detail="Whiteboard not found")
    comment = service.add_comment(whiteboard_id=board_id, **payload.model_dump())
    return WhiteboardCommentOut.model_validate(comment)


@router.get("/{board_id}/comments", response_model=list[WhiteboardCommentOut])
def list_comments(board_id: int, session: Session = Depends(get_db_session)) -> list[WhiteboardCommentOut]:
    service = WhiteboardService(session)
    if not service.get_whiteboard(board_id):
        raise HTTPException(status_code=404, detail="Whiteboard not found")
    comments = service.list_comments(whiteboard_id=board_id)
    return [WhiteboardCommentOut.model_validate(item) for item in comments]

