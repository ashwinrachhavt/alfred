"""Research agents: CRUD for ResearchAgentSpec + streaming run endpoint.

Routes:
  POST    /api/research/agents           create spec
  GET     /api/research/agents           list specs (system + user-owned)
  GET     /api/research/agents/{id}      fetch spec
  PATCH   /api/research/agents/{id}      update spec
  DELETE  /api/research/agents/{id}      delete spec (non-system only)
  GET     /api/research/agents/catalog   tool catalog for the UI builder
  POST    /api/research/run              run a deep research task (SSE)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from alfred.api.dependencies import get_db_session
from alfred.models.research_agent import ResearchAgentSpecRow
from alfred.schemas.research_agent import (
    ResearchAgentSpecCreate,
    ResearchAgentSpecOut,
    ResearchAgentSpecUpdate,
    RunRequest,
    ToolCatalogEntry,
)
from alfred.services.deep_research import DeepResearchService, get_tool_registry

router = APIRouter(prefix="/api/research/agents", tags=["research-agents"])
run_router = APIRouter(prefix="/api/research", tags=["research-agents"])
logger = logging.getLogger(__name__)


def _to_out(row: ResearchAgentSpecRow) -> ResearchAgentSpecOut:
    return ResearchAgentSpecOut.model_validate(row, from_attributes=True)


# -- CRUD -------------------------------------------------------------------


@router.get("/catalog", response_model=list[ToolCatalogEntry])
def get_catalog() -> list[ToolCatalogEntry]:
    """Return the catalog of tools available for inclusion in a spec."""
    return get_tool_registry().catalog()


@router.get("", response_model=list[ResearchAgentSpecOut])
def list_specs(db: Session = Depends(get_db_session)) -> list[ResearchAgentSpecOut]:
    rows = db.exec(select(ResearchAgentSpecRow).order_by(ResearchAgentSpecRow.name)).all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=ResearchAgentSpecOut, status_code=status.HTTP_201_CREATED)
def create_spec(
    body: ResearchAgentSpecCreate,
    db: Session = Depends(get_db_session),
) -> ResearchAgentSpecOut:
    existing = db.exec(
        select(ResearchAgentSpecRow).where(ResearchAgentSpecRow.slug == body.slug)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Slug '{body.slug}' already exists")

    registry = get_tool_registry()
    try:
        registry.resolve(body.tool_allowlist)
        for sa in body.subagents:
            registry.resolve(sa.tools)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    row = ResearchAgentSpecRow(
        slug=body.slug,
        name=body.name,
        description=body.description,
        instructions=body.instructions,
        model_name=body.model_name,
        tool_allowlist=list(body.tool_allowlist),
        connector_bindings=dict(body.connector_bindings),
        subagents=[sa.model_dump() for sa in body.subagents],
        is_system=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.get("/{spec_id}", response_model=ResearchAgentSpecOut)
def get_spec(spec_id: int, db: Session = Depends(get_db_session)) -> ResearchAgentSpecOut:
    row = db.get(ResearchAgentSpecRow, spec_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Spec not found")
    return _to_out(row)


@router.patch("/{spec_id}", response_model=ResearchAgentSpecOut)
def update_spec(
    spec_id: int,
    body: ResearchAgentSpecUpdate,
    db: Session = Depends(get_db_session),
) -> ResearchAgentSpecOut:
    row = db.get(ResearchAgentSpecRow, spec_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Spec not found")
    if row.is_system:
        raise HTTPException(status_code=403, detail="System specs are not editable")

    registry = get_tool_registry()
    if body.tool_allowlist is not None:
        try:
            registry.resolve(body.tool_allowlist)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row.tool_allowlist = list(body.tool_allowlist)

    if body.subagents is not None:
        try:
            for sa in body.subagents:
                registry.resolve(sa.tools)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row.subagents = [sa.model_dump() for sa in body.subagents]

    for field in ("name", "description", "instructions", "model_name", "connector_bindings"):
        value = getattr(body, field)
        if value is not None:
            setattr(row, field, value)

    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.delete("/{spec_id}")
def delete_spec(spec_id: int, db: Session = Depends(get_db_session)) -> dict[str, bool]:
    row = db.get(ResearchAgentSpecRow, spec_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Spec not found")
    if row.is_system:
        raise HTTPException(status_code=403, detail="System specs are not deletable")
    db.delete(row)
    db.commit()
    return {"ok": True}


# -- Streaming run ----------------------------------------------------------


@run_router.post("/run")
async def run_deep_research(
    body: RunRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    """Run a deep research task and stream SSE events back to the client."""
    if not body.topic.strip():
        raise HTTPException(status_code=422, detail="topic is required")

    if body.agent_spec_id is None and body.inline_spec is None:
        raise HTTPException(
            status_code=422,
            detail="One of agent_spec_id or inline_spec is required",
        )

    service = DeepResearchService(db)
    try:
        spec: Any
        if body.agent_spec_id is not None:
            spec = service.load_spec(body.agent_spec_id)
        else:
            spec = body.inline_spec
        agent = service.build_agent(spec)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def gen():
        async for _event_name, _data, sse_str in service.stream_run(
            agent=agent,
            topic=body.topic,
            thread_id=body.thread_id,
            model_name=getattr(spec, "model_name", None),
        ):
            if await request.is_disconnected():
                return
            yield sse_str

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
