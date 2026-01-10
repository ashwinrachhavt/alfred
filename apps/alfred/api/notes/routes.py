from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from alfred.api.dependencies import get_db_session
from alfred.schemas.notes import (
    NoteCreateRequest,
    NoteMoveRequest,
    NoteResponse,
    NotesListResponse,
    NoteSummary,
    NoteTreeNode,
    NoteTreeResponse,
    NoteUpdateRequest,
)
from alfred.services.notes_service import (
    NoteMoveConflictError,
    NoteNotFoundError,
    NotesService,
    WorkspaceNotFoundError,
)

router = APIRouter(prefix="/api/v1", tags=["notes"])


def _as_uuid(value: str | None, *, field_name: str) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid {field_name}: {value}") from exc


def _note_summary(row) -> NoteSummary:  # noqa: ANN001 - SQLModel row
    return NoteSummary(
        id=str(row.id),
        title=row.title,
        icon=row.icon,
        cover_image=row.cover_image,
        parent_id=str(row.parent_id) if row.parent_id else None,
        workspace_id=str(row.workspace_id),
        position=int(row.position),
        is_archived=bool(row.is_archived),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _note_response(row) -> NoteResponse:  # noqa: ANN001 - SQLModel row
    return NoteResponse(
        **_note_summary(row).model_dump(),
        content_markdown=row.content_markdown or "",
        content_json=row.content_json,
        created_by=row.created_by,
        last_edited_by=row.last_edited_by,
    )


@router.get("/workspaces", response_model=list[dict[str, Any]])
def list_workspaces(
    user_id: int | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    svc = NotesService(session)
    rows = svc.list_workspaces(user_id=user_id)
    return [
        {
            "id": str(w.id),
            "name": w.name,
            "icon": w.icon,
            "user_id": w.user_id,
            "settings": w.settings or {},
            "created_at": w.created_at,
            "updated_at": w.updated_at,
        }
        for w in rows
    ]


@router.post("/workspaces", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: dict[str, Any],
    user_id: int | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    svc = NotesService(session)
    try:
        row = svc.create_workspace(
            name=str(payload.get("name") or ""),
            icon=payload.get("icon"),
            user_id=user_id,
            settings=payload.get("settings"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": str(row.id),
        "name": row.name,
        "icon": row.icon,
        "user_id": row.user_id,
        "settings": row.settings or {},
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreateRequest,
    user_id: int | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> NoteResponse:
    svc = NotesService(session)
    try:
        row = svc.create_note(
            workspace_id=payload.workspace_id,
            parent_id=payload.parent_id,
            title=payload.title,
            icon=payload.icon,
            cover_image=payload.cover_image,
            content_markdown=payload.content_markdown,
            content_json=payload.content_json,
            user_id=user_id,
        )
    except NoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoteMoveConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _note_response(row)


@router.get("/notes/tree", response_model=NoteTreeResponse)
def tree(
    workspace_id: str,
    include_archived: bool = Query(default=False),
    session: Session = Depends(get_db_session),
) -> NoteTreeResponse:
    svc = NotesService(session)
    try:
        rows = svc.tree(workspace_id=workspace_id, include_archived=include_archived)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    by_id: dict[str, NoteTreeNode] = {}
    root: list[NoteTreeNode] = []

    for row in rows:
        node = NoteTreeNode(note=_note_summary(row), children=[])
        by_id[str(row.id)] = node

    for row in rows:
        node = by_id[str(row.id)]
        parent = str(row.parent_id) if row.parent_id else None
        if parent and parent in by_id:
            by_id[parent].children.append(node)
        else:
            root.append(node)

    def _sort_children(n: NoteTreeNode) -> None:
        n.children.sort(key=lambda child: child.note.position)
        for child in n.children:
            _sort_children(child)

    root.sort(key=lambda n: n.note.position)
    for n in root:
        _sort_children(n)

    return NoteTreeResponse(workspace_id=workspace_id, items=root)


@router.get("/notes/{note_id}", response_model=NoteResponse)
def get_note(note_id: uuid.UUID, session: Session = Depends(get_db_session)) -> NoteResponse:
    svc = NotesService(session)
    try:
        row = svc.get_note(note_id)
    except NoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _note_response(row)


@router.patch("/notes/{note_id}", response_model=NoteResponse)
def update_note(
    note_id: uuid.UUID,
    payload: NoteUpdateRequest,
    user_id: int | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> NoteResponse:
    svc = NotesService(session)
    try:
        row = svc.update_note(
            note_id,
            title=payload.title,
            icon=payload.icon,
            cover_image=payload.cover_image,
            content_markdown=payload.content_markdown,
            content_json=payload.content_json,
            is_archived=payload.is_archived,
            user_id=user_id,
        )
    except NoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _note_response(row)


@router.delete("/notes/{note_id}", response_model=dict[str, Any])
def delete_note(
    note_id: uuid.UUID,
    user_id: int | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    svc = NotesService(session)
    try:
        row = svc.archive_note(note_id, user_id=user_id)
    except NoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "id": str(row.id)}


@router.get("/notes", response_model=NotesListResponse)
def list_notes(
    workspace_id: str,
    q: str | None = Query(default=None),
    parent_id: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> NotesListResponse:
    svc = NotesService(session)
    parent_uuid = _as_uuid(parent_id, field_name="parent_id") if parent_id is not None else None
    try:
        rows, total = svc.list_notes(
            workspace_id=workspace_id,
            q=q,
            parent_id=parent_uuid,
            skip=skip,
            limit=limit,
            include_archived=include_archived,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return NotesListResponse(
        items=[_note_summary(r) for r in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/notes/{note_id}/children", response_model=list[NoteSummary])
def list_children(
    note_id: uuid.UUID,
    include_archived: bool = Query(default=False),
    session: Session = Depends(get_db_session),
) -> list[NoteSummary]:
    svc = NotesService(session)
    try:
        rows = svc.list_children(note_id, include_archived=include_archived)
    except NoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_note_summary(r) for r in rows]


@router.post("/notes/{note_id}/move", response_model=NoteResponse)
def move_note(
    note_id: uuid.UUID,
    payload: NoteMoveRequest,
    user_id: int | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> NoteResponse:
    svc = NotesService(session)
    try:
        row = svc.move_note(
            note_id,
            parent_id=payload.parent_id,
            position=payload.position,
            user_id=user_id,
        )
    except NoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoteMoveConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _note_response(row)
